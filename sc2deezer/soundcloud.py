"""Lecture des playlists SoundCloud, téléchargement en MP3 et tags (titre, artiste, cover)."""
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests
import yt_dlp
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError

from .deezer import UA


class PlaylistError(Exception):
    pass


class _SilentLogger:
    """Les erreurs de yt-dlp remontent en exception : on les affiche nous-mêmes."""
    def debug(self, msg):
        pass

    warning = error = debug


BASE_OPTS = {"quiet": True, "no_warnings": True, "noprogress": True, "logger": _SilentLogger()}


def normalize_url(url):
    url = (url or "").strip()
    if not url.startswith("http"):
        url = "https://" + url
    host = urlparse(url).hostname or ""
    if host == "on.soundcloud.com":  # liens courts « Partager » de l'appli mobile
        try:
            url = requests.head(url, allow_redirects=True, timeout=30, headers={"User-Agent": UA}).url
        except requests.RequestException:
            pass
        host = urlparse(url).hostname or ""
    if not host.endswith("soundcloud.com"):
        raise PlaylistError("Ce lien ne vient pas de SoundCloud. Il doit ressembler à "
                            "https://soundcloud.com/artiste/sets/nom-de-la-playlist")
    return url


def playlist(url):
    try:
        with yt_dlp.YoutubeDL({**BASE_OPTS, "extract_flat": "in_playlist"}) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise PlaylistError("Impossible de lire cette playlist SoundCloud. Vérifie le lien, "
                            "et qu'elle est bien publique (ou que le lien privé est complet).") from exc
    if info.get("_type") != "playlist":
        raise PlaylistError("Ce lien mène à un seul son, pas à une playlist. "
                            "Ouvre la playlist sur SoundCloud et copie son lien.")
    entries = [e for e in info.get("entries") or [] if e]
    if not entries:
        raise PlaylistError("Cette playlist SoundCloud est vide.")
    info["entries"] = entries
    return info


def playlist_cover_url(url):
    """yt-dlp ne donne pas l'artwork d'une playlist : on le lit dans la page (og:image)."""
    try:
        html = requests.get(url, headers={"User-Agent": UA}, timeout=30).text
    except requests.RequestException:
        return None
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    return m.group(1) if m else None


def _image_mime(data):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return None


def _fetch_image(url, max_bytes=8 * 1024 * 1024):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    except requests.RequestException:
        return None
    if r.status_code != 200 or len(r.content) > max_bytes:
        return None
    mime = _image_mime(r.content)
    return (r.content, mime) if mime else None


def best_artwork(url, prefer_original=False):
    """Télécharge un artwork SoundCloud ; renvoie (octets, type MIME) ou None.

    artworks-xxx-t500x500.jpg existe aussi en -original (pleine résolution).
    """
    m = re.match(r"(.*-)(?:large|t\d+x\d+|crop|original)(\.\w+)$", url or "")
    if m:
        base, ext = m.groups()
        sized = f"{base}t500x500{ext}"
        candidates = [f"{base}original{ext}", f"{base}original.png", sized] if prefer_original else [sized]
    else:
        candidates = [url] if url else []
    for candidate in candidates:
        img = _fetch_image(candidate)
        if img:
            return img
    return None


def ffmpeg_location():
    system = shutil.which("ffmpeg")
    if system:
        return system
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def download_track(entry_url, out_dir, ffmpeg):
    opts = {
        **BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": str(Path(out_dir) / "%(id)s.%(ext)s"),
        "ffmpeg_location": ffmpeg,
        # Deezer recommande du MP3 à débit constant (le VBR peut mal se lire).
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "256"}],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(entry_url, download=True)
    return info, Path(info["requested_downloads"][0]["filepath"])


def _same_artist(a, b):
    a, b = a.casefold().strip(), b.casefold().strip()
    return bool(a and b) and (a in b or b in a)


def track_metadata(info):
    """Renvoie (titre, artiste, url de l'artwork) d'un son SoundCloud."""
    title = " ".join((info.get("track") or info.get("title") or str(info["id"])).split())
    artist = " ".join((info.get("artist") or ", ".join(info.get("artists") or [])).split())
    if " - " in title:
        # Beaucoup de sons sont titrés « Artiste - Titre » : on évite « Artiste - Artiste - Titre ».
        prefix, rest = (part.strip() for part in title.split(" - ", 1))
        if not artist:
            artist, title = prefix, rest
        elif _same_artist(prefix, artist):
            title = rest
    artist = artist or info.get("uploader") or "SoundCloud"
    thumbs = {t.get("id"): t.get("url") for t in info.get("thumbnails") or []}
    return title, artist, thumbs.get("t500x500") or info.get("thumbnail")


def tag_mp3(path, title, artist, cover):
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("APIC")
    tags["TIT2"] = TIT2(encoding=3, text=title)
    tags["TPE1"] = TPE1(encoding=3, text=artist)
    tags["TALB"] = TALB(encoding=3, text=title)
    if cover:
        data, mime = cover
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data))
    tags.save(path, v2_version=3)
