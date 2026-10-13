"""Le transfert complet : SoundCloud -> MP3 -> « Mes MP3 » Deezer -> playlist + cover (+ Coups de cœur).

Marche avec une playlist ou un seul son. Tout l'avancement est noté dans state.json,
à côté des MP3 : relancer le même lien reprend là où on s'était arrêté, sans rien
re-télécharger ni ré-envoyer.
"""
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests

from . import applemusic, soundcloud
from .config import default_output_dir
from .deezer import Deezer
from .soundcloud import PlaylistError

SINGLES_FOLDER = "Sons seuls"
APPLE_FOLDER = "Pour Apple Music"


class Cancelled(Exception):
    pass


@dataclass
class Result:
    url: str  # la playlist Deezer, ou les Coups de cœur / Mes MP3 pour un son seul
    title: str
    profile: str
    count: int
    folder: Path
    kind: str = "playlist"  # ou "track"
    liked: int = 0
    failures: list = field(default_factory=list)
    destination: str = "deezer"  # « deezer », « itunes » ou « folder » (dossier à glisser dans Apple Music)
    to_import: Path = None  # mode « folder » : le dossier (ou le MP3) à glisser dans Apple Music


def file_name(text, max_len=120):
    """Nom de fichier lisible et valide sous Windows."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")[:max_len] or "son"


def slugify(text, max_len=60):
    text = re.sub(r"[^\w\-]+", "_", text).strip("_")
    return text[:max_len] or "playlist"


def file_md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def friendly_error(exc):
    text = str(exc)
    if "DRM" in text:
        return "son protégé par SoundCloud (DRM), impossible à télécharger"
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return "problème de connexion internet (ou SoundCloud / Deezer injoignable)"
    return re.sub(r"^ERROR: (\[[^\]]+\] )?([\w-]+: )?", "", text)


def load_state(path, legacy_owner=None):
    """MP3 téléchargés (communs) + ce qui a été envoyé : Deezer profil par profil, iTunes."""
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    state.setdefault("tracks", {})
    by_profile = state.setdefault("deezer", {})
    # Ancien format (un seul compte) : tout avait été envoyé sur le profil principal.
    legacy = "deezer_playlist_id" in state or any("sng_id" in t for t in state["tracks"].values())
    if legacy and legacy_owner is not None:
        legacy = by_profile.setdefault(str(legacy_owner), {})
        legacy.setdefault("songs", {})
        legacy["playlist_id"] = state.pop("deezer_playlist_id", None)
        if state.pop("cover_done", None):
            legacy["cover_done"] = True
        for sc_id, track in state["tracks"].items():
            song = {k: track.pop(k) for k in ("sng_id", "added") if k in track}
            if song:
                legacy["songs"][sc_id] = song
    return state


def ensure_mp3(folder, state, sc_id, source_url, ffmpeg, save):
    """Le MP3 tagué (titre, artiste, cover) du son, téléchargé seulement s'il manque. Renvoie son suivi."""
    track = state["tracks"].setdefault(sc_id, {})
    if not track.get("file") or not (folder / track["file"]).exists():
        info, path = soundcloud.download_track(source_url, folder, ffmpeg)
        title, artist, artwork = soundcloud.track_metadata(info)
        soundcloud.tag_mp3(path, title, artist, soundcloud.best_artwork(artwork))
        track.update(file=path.name, title=title, artist=artist)
        save()
    return track


def known_uploads(root, user_id):
    """Sons déjà envoyés sur ce profil, depuis n'importe quel dossier (playlists, sons seuls).

    Renvoie {id SoundCloud: (id Deezer, titre, artiste)}.
    """
    known = {}
    for path in Path(root).glob("*/state.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for sc_id, song in ((state.get("deezer") or {}).get(str(user_id)) or {}).get("songs", {}).items():
            track = (state.get("tracks") or {}).get(sc_id) or {}
            if song.get("sng_id") and track.get("title"):
                known[sc_id] = (song["sng_id"], track["title"], track.get("artist", ""))
    return known


class Job:
    """Un dossier de MP3 + son suivi, pour un profil Deezer donné."""

    def __init__(self, dz, folder):
        self.dz = dz
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.state_path = folder / "state.json"
        self.state = load_state(self.state_path, dz.main_user_id)
        self.mine = self.state["deezer"].setdefault(str(dz.user_id), {})
        self.songs = self.mine.setdefault("songs", {})
        self.ffmpeg = soundcloud.ffmpeg_location()
        # MP3 déjà dans « Mes MP3 » (copie interrompue, suivi effacé…) : Deezer garde l'empreinte MD5
        # du fichier envoyé, ce qui permet de les reconnaître à l'identique et d'éviter les doublons.
        self.existing = {str(s.get("MD5_ORIGIN") or "").split(".")[0]: int(s["SNG_ID"]) for s in dz.personal_songs()}
        # Un même son retéléchargé n'a pas la même empreinte : on s'appuie aussi sur les autres copies.
        self.known = known_uploads(folder.parent, dz.user_id)
        self.live_ids = set(self.existing.values())

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")

    def copy_track(self, sc_id, source_url):
        """Télécharge (si besoin) un son, puis l'envoie dans « Mes MP3 ». Renvoie (libellé, statut)."""
        track = self.state["tracks"].setdefault(sc_id, {})
        song = self.songs.setdefault(sc_id, {})
        if song.get("sng_id") and track.get("title"):  # déjà sur Deezer : même plus besoin du MP3 local
            return f"{track['artist']} - {track['title']}", "already"
        known = self.known.get(sc_id)
        if known and known[0] in self.live_ids:
            # Déjà sur ce profil (copié avec une autre playlist ou en son seul) : rien à télécharger.
            song["sng_id"] = known[0]
            track.setdefault("title", known[1])
            track.setdefault("artist", known[2])
            self.save()
            return f"{track['artist']} - {track['title']}", "already"
        ensure_mp3(self.folder, self.state, sc_id, source_url, self.ffmpeg, self.save)
        label = f"{track['artist']} - {track['title']}"
        reused = self.existing.get(file_md5(self.folder / track["file"]))
        song["sng_id"] = reused or self.dz.upload_mp3(self.folder / track["file"])
        self.save()
        return label, "already" if reused else "ok"

    def like(self, songs, emit):
        """Like les sons qui ne l'ont jamais été par le programme (un like retiré à la main n'est pas remis)."""
        todo = [s for s in songs if s.get("sng_id") and not s.get("liked")]
        if todo:
            emit("status", text=f"Ajout de {len(todo)} son(s) à tes Coups de cœur…")
            self.dz.like_songs([s["sng_id"] for s in todo])
            for s in todo:
                s["liked"] = True
            self.save()
        return len(todo)


def run(url, arl, *, profile_id=None, name=None, public=False, like=None, out_root=None, emit=None, stop=None):
    """Copie une playlist ou un son. `like` : ajouter aux Coups de cœur (None = oui pour un son seul,
    non pour une playlist). `emit(kind, **data)` reçoit l'avancement, `stop` (threading.Event) l'interrompt."""
    emit = emit or (lambda kind, **data: None)

    def check_stop():
        if stop is not None and stop.is_set():
            raise Cancelled()

    url = soundcloud.normalize_url(url)
    emit("status", text="Connexion à Deezer…")
    dz = Deezer(arl, profile_id)
    emit("connected", user=dz.user_name)
    emit("status", text="Lecture du lien SoundCloud…")
    info = soundcloud.fetch(url)
    root = Path(out_root or default_output_dir())
    if info.get("_type") == "playlist":
        return _run_playlist(dz, url, info, root, name, public, bool(like), emit, check_stop)
    return _run_single(dz, url, info, root, like is not False, emit)


def _run_single(dz, url, info, root, like, emit):
    job = Job(dz, root / SINGLES_FOLDER)
    emit("playlist", title=info.get("title") or "son", total=1, folder=job.folder, source="track")
    emit("progress", index=1, total=1)
    sc_id = str(info["id"])
    label, status = job.copy_track(sc_id, info.get("webpage_url") or url)
    emit("track", index=1, total=1, text=label, status=status)
    liked = job.like([job.songs[sc_id]], emit) if like else 0
    return Result(
        url=dz.library_url("loved" if like else "personal_song"),
        title=label,
        profile=dz.user_name,
        count=1,
        folder=job.folder,
        kind="track",
        liked=liked,
    )


def _run_playlist(dz, url, pl, root, name, public, like, emit, check_stop):
    entries = pl["entries"]
    total = len(entries)
    sc_title = pl.get("title") or "SoundCloud"
    job = Job(dz, root / f"{slugify(sc_title)}-{pl['id']}")
    emit("playlist", title=sc_title, total=total, folder=job.folder, source="playlist")
    failures = []

    # 1. Téléchargement + tags + envoi dans « Mes MP3 »
    for n, entry in enumerate(entries, 1):
        check_stop()
        sc_id = str(entry.get("id"))
        emit("progress", index=n, total=total)
        try:
            label, status = job.copy_track(sc_id, entry["url"])
            emit("track", index=n, total=total, text=label, status=status)
        except Exception as exc:  # un son en échec ne bloque pas les autres
            track = job.state["tracks"].get(sc_id, {})
            what = track.get("title") or entry.get("title") or entry.get("url") or sc_id
            why = friendly_error(exc)
            failures.append((what, why))
            emit("track", index=n, total=total, text=what, status="failed", detail=why)

    check_stop()
    ordered = [job.songs[str(e.get("id"))] for e in entries]
    if not any(s.get("sng_id") for s in ordered):
        raise PlaylistError("Aucun son de cette playlist n'a pu être copié.")

    # 2. Playlist Deezer sur ce profil (réutilisée quand on relance)
    mine = job.mine
    playlist_id = mine.get("playlist_id")
    if playlist_id and not dz.playlist_exists(playlist_id):
        playlist_id = None
    if not playlist_id:
        emit("status", text="Création de la playlist sur Deezer…")
        playlist_id = dz.create_playlist(name or sc_title, f"Importée depuis SoundCloud : {url}", public)
        mine["playlist_id"] = playlist_id
        mine.pop("cover_done", None)
        for s in ordered:
            s.pop("added", None)
        job.save()

    to_add = [s for s in ordered if s.get("sng_id") and not s.get("added")]
    if to_add:
        emit("status", text=f"Ajout de {len(to_add)} son(s) à la playlist…")
        dz.add_songs(playlist_id, [s["sng_id"] for s in to_add])
        for s in to_add:
            s["added"] = True
        job.save()

    # 3. Cover de la playlist = artwork SoundCloud d'origine
    if not mine.get("cover_done"):
        emit("status", text="Ajout de la cover de la playlist…")
        cover = soundcloud.best_artwork(soundcloud.playlist_cover_url(url), prefer_original=True)
        if cover:
            data, mime = cover
            cover_path = job.folder / ("cover.png" if mime == "image/png" else "cover.jpg")
            cover_path.write_bytes(data)
            try:
                dz.set_playlist_cover(playlist_id, cover_path, mime)
                mine["cover_done"] = True
                job.save()
            except Exception as exc:
                failures.append(("cover de la playlist", friendly_error(exc)))

    # 4. Coups de cœur, si demandé
    liked = job.like(ordered, emit) if like else 0

    return Result(
        url=f"https://www.deezer.com/fr/playlist/{playlist_id}",
        title=name or sc_title,
        profile=dz.user_name,
        count=sum(1 for s in ordered if s.get("added")),
        folder=job.folder,
        kind="playlist",
        liked=liked,
        failures=failures,
    )


def run_apple(url, *, name=None, out_root=None, emit=None, stop=None, mode=None):
    """Copie une playlist ou un son vers Apple Music.

    mode « itunes » : import automatique dans iTunes, playlist comprise.
    mode « folder » : prépare un dossier (ou un MP3) à glisser dans l'appli Apple Music. Seuls les sons
    jamais livrés y sont mis, et rien n'est effacé ensuite : Apple Music lit les sons à cet endroit.
    """
    emit = emit or (lambda kind, **data: None)

    def check_stop():
        if stop is not None and stop.is_set():
            raise Cancelled()

    mode = mode or applemusic.detect()
    url = soundcloud.normalize_url(url)
    emit("status", text="Lecture du lien SoundCloud…")
    info = soundcloud.fetch(url)
    single = info.get("_type") != "playlist"
    entries = [{"id": info["id"], "url": info.get("webpage_url") or url}] if single else info["entries"]
    sc_title = info.get("title") or "SoundCloud"
    title = sc_title if single else (name or sc_title)
    root = Path(out_root or default_output_dir())
    folder = root / (SINGLES_FOLDER if single else f"{slugify(sc_title)}-{info['id']}")
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / "state.json"
    state = load_state(state_path)

    def save():
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    itunes = playlist = None
    in_playlist = set()
    mine = state.setdefault("itunes" if mode == "itunes" else "apple_folder", {})
    songs = mine.setdefault("songs", {})
    if mode == "itunes":
        emit("status", text="Ouverture d'iTunes…")
        itunes = applemusic.ITunes()
        if not single:
            playlist = itunes.playlist(mine.get("playlist"))
            if playlist is None:
                emit("status", text="Création de la playlist dans iTunes…")
                playlist = itunes.create_playlist(title)
                mine["playlist"] = itunes.ids(playlist)
                save()
            in_playlist = itunes.playlist_track_ids(playlist)

    total = len(entries)
    emit("playlist", title=sc_title, total=total, folder=folder, source="track" if single else "playlist")
    ffmpeg = soundcloud.ffmpeg_location()
    failures, ready, fresh = [], [], []
    for n, entry in enumerate(entries, 1):
        check_stop()
        sc_id = str(entry.get("id"))
        emit("progress", index=n, total=total)
        try:
            track = ensure_mp3(folder, state, sc_id, entry["url"], ffmpeg, save)
            label = f"{track['artist']} - {track['title']}"
            status = "already" if songs.get(sc_id) else "ok"
            if itunes:
                existing = itunes.track(songs.get(sc_id))
                if existing is None:
                    added = itunes.add_file(folder / track["file"], playlist)
                    songs[sc_id] = itunes.ids(added)
                    in_playlist.add(tuple(songs[sc_id]))
                    status = "ok"
                    save()
                elif playlist is not None and tuple(songs[sc_id]) not in in_playlist:
                    itunes.add_track(playlist, existing)
                    in_playlist.add(tuple(songs[sc_id]))
            elif not songs.get(sc_id):
                fresh.append((n, sc_id, track))
            ready.append(track)
            emit("track", index=n, total=total, text=label, status=status)
        except Exception as exc:  # un son en échec ne bloque pas les autres
            what = state["tracks"].get(sc_id, {}).get("title") or entry.get("title") or entry.get("url") or sc_id
            why = friendly_error(exc)
            failures.append((what, why))
            emit("track", index=n, total=total, text=what, status="failed", detail=why)

    check_stop()
    if not ready:
        raise PlaylistError("Aucun son n'a pu être préparé.")

    to_import = None
    if mode != "itunes" and fresh:
        emit("status", text="Préparation du dossier pour Apple Music…")
        base = root / APPLE_FOLDER / (SINGLES_FOLDER if single else file_name(title))
        if single:
            to_import = base
        else:
            batches = [p for p in base.glob("*") if p.is_dir()] if base.exists() else []
            to_import = base / f"{len(batches) + 1} - ajout du {datetime.now():%d-%m-%Y %Hh%M}"
        to_import.mkdir(parents=True, exist_ok=True)
        for n, sc_id, track in fresh:
            label = f"{track['artist']} - {track['title']}"
            target = to_import / f"{file_name(label) if single else f'{n:03d} - {file_name(label)}'}.mp3"
            shutil.copy2(folder / track["file"], target)
            songs[sc_id] = target.name
        if not single:
            applemusic.write_m3u8(to_import / f"{file_name(title)}.m3u8",
                                  [{**t, "file": f"{n:03d} - {file_name(t['artist'] + ' - ' + t['title'])}.mp3"}
                                   for n, _, t in fresh])
            if not batches:  # 1re fois : la cover SoundCloud, à mettre comme illustration de la playlist
                cover = soundcloud.best_artwork(soundcloud.playlist_cover_url(url), prefer_original=True)
                if cover:
                    data, mime = cover
                    (to_import / f"cover de la playlist.{'png' if mime == 'image/png' else 'jpg'}").write_bytes(data)
        else:
            to_import = to_import / songs[fresh[0][1]]
        save()

    return Result(
        url="",
        title=f"{ready[0]['artist']} - {ready[0]['title']}" if single else title,
        profile="iTunes" if itunes else "Apple Music",
        count=len(ready),
        folder=folder,
        kind="track" if single else "playlist",
        failures=failures,
        destination=mode,
        to_import=to_import,
    )
