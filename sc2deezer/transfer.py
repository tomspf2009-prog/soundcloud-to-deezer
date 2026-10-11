"""Le transfert complet : SoundCloud -> MP3 -> « Mes MP3 » Deezer -> playlist + cover.

Tout l'avancement est noté dans state.json, à côté des MP3 : relancer la même
playlist reprend là où on s'était arrêté, sans rien re-télécharger ni ré-envoyer.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import soundcloud
from .config import default_output_dir
from .deezer import Deezer
from .soundcloud import PlaylistError


class Cancelled(Exception):
    pass


@dataclass
class Result:
    playlist_url: str
    title: str
    profile: str
    count: int
    folder: Path
    failures: list = field(default_factory=list)


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


def load_state(path, legacy_owner):
    """MP3 téléchargés (communs) + ce qui a été envoyé, profil Deezer par profil."""
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    state.setdefault("tracks", {})
    by_profile = state.setdefault("deezer", {})
    # Ancien format (un seul compte) : tout avait été envoyé sur le profil principal.
    if "deezer_playlist_id" in state or any("sng_id" in t for t in state["tracks"].values()):
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


def run(url, arl, *, profile_id=None, name=None, public=False, out_root=None, emit=None, stop=None):
    """Copie la playlist. `emit(kind, **data)` reçoit l'avancement, `stop` (threading.Event) l'interrompt."""
    emit = emit or (lambda kind, **data: None)

    def check_stop():
        if stop is not None and stop.is_set():
            raise Cancelled()

    url = soundcloud.normalize_url(url)
    emit("status", text="Connexion à Deezer…")
    dz = Deezer(arl, profile_id)
    emit("connected", user=dz.user_name)

    emit("status", text="Lecture de la playlist SoundCloud…")
    pl = soundcloud.playlist(url)
    entries = pl["entries"]
    total = len(entries)
    sc_title = pl.get("title") or "SoundCloud"
    folder = Path(out_root or default_output_dir()) / f"{slugify(sc_title)}-{pl['id']}"
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / "state.json"
    state = load_state(state_path, dz.main_user_id)
    mine = state["deezer"].setdefault(str(dz.user_id), {})
    songs = mine.setdefault("songs", {})

    def save():
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    emit("playlist", title=sc_title, total=total, folder=folder)
    ffmpeg = soundcloud.ffmpeg_location()
    # MP3 déjà dans « Mes MP3 » (copie interrompue, suivi effacé…) : Deezer garde l'empreinte MD5
    # du fichier envoyé, ce qui permet de les reconnaître à l'identique et d'éviter les doublons.
    existing = {str(s.get("MD5_ORIGIN") or "").split(".")[0]: int(s["SNG_ID"]) for s in dz.personal_songs()}
    failures = []

    # 1. Téléchargement + tags + envoi dans « Mes MP3 »
    for n, entry in enumerate(entries, 1):
        check_stop()
        sc_id = str(entry.get("id"))
        track = state["tracks"].setdefault(sc_id, {})
        song = songs.setdefault(sc_id, {})
        emit("progress", index=n, total=total)
        try:
            if not track.get("file") or not (folder / track["file"]).exists():
                info, path = soundcloud.download_track(entry["url"], folder, ffmpeg)
                title, artist, artwork = soundcloud.track_metadata(info)
                soundcloud.tag_mp3(path, title, artist, soundcloud.best_artwork(artwork))
                track.update(file=path.name, title=title, artist=artist)
                save()
            label = f"{track['artist']} - {track['title']}"
            if song.get("sng_id"):
                emit("track", index=n, total=total, text=label, status="already")
                continue
            reused = existing.get(file_md5(folder / track["file"]))
            song["sng_id"] = reused or dz.upload_mp3(folder / track["file"])
            save()
            emit("track", index=n, total=total, text=label, status="already" if reused else "ok")
        except Exception as exc:  # un son en échec ne bloque pas les autres
            what = track.get("title") or entry.get("title") or entry.get("url") or sc_id
            why = friendly_error(exc)
            failures.append((what, why))
            emit("track", index=n, total=total, text=what, status="failed", detail=why)

    check_stop()
    ordered = [songs[str(e.get("id"))] for e in entries]
    if not any(s.get("sng_id") for s in ordered):
        raise PlaylistError("Aucun son de cette playlist n'a pu être copié.")

    # 2. Playlist Deezer sur ce profil (réutilisée quand on relance)
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
        save()

    to_add = [s for s in ordered if s.get("sng_id") and not s.get("added")]
    if to_add:
        emit("status", text=f"Ajout de {len(to_add)} son(s) à la playlist…")
        dz.add_songs(playlist_id, [s["sng_id"] for s in to_add])
        for s in to_add:
            s["added"] = True
        save()

    # 3. Cover de la playlist = artwork SoundCloud d'origine
    if not mine.get("cover_done"):
        emit("status", text="Ajout de la cover de la playlist…")
        cover = soundcloud.best_artwork(soundcloud.playlist_cover_url(url), prefer_original=True)
        if cover:
            data, mime = cover
            cover_path = folder / ("cover.png" if mime == "image/png" else "cover.jpg")
            cover_path.write_bytes(data)
            try:
                dz.set_playlist_cover(playlist_id, cover_path, mime)
                mine["cover_done"] = True
                save()
            except Exception as exc:
                failures.append(("cover de la playlist", friendly_error(exc)))

    return Result(
        playlist_url=f"https://www.deezer.com/fr/playlist/{playlist_id}",
        title=name or sc_title,
        profile=dz.user_name,
        count=sum(1 for s in ordered if s.get("added")),
        folder=folder,
        failures=failures,
    )
