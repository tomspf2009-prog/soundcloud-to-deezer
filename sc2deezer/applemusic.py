"""Apple Music : import automatique via iTunes, ou dossier prêt à glisser dans l'appli Apple Music.

Apple ne permet à aucun programme d'envoyer de la musique dans la bibliothèque en ligne.
- iTunes (Windows) se pilote par programme (COM) : on y importe les MP3 et on crée la playlist.
- L'appli Apple Music (Windows) ne se pilote pas : on prépare un dossier à y glisser.
Avec un abonnement Apple Music et la synchronisation de la bibliothèque, les sons importés
arrivent ensuite sur l'iPhone.
"""
import os
import sys
import time
from pathlib import Path


class AppleMusicError(Exception):
    pass


def apple_music_app_installed():
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"
    return sys.platform == "win32" and any(packages.glob("AppleInc.AppleMusic*"))


def itunes_installed():
    if sys.platform != "win32":
        return False
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "iTunes.Application").Close()
        return True
    except OSError:
        return False


def detect():
    """« itunes » : import automatique possible. « folder » : dossier à glisser dans Apple Music."""
    # Une fois l'appli Apple Music installée, iTunes ne gère plus la musique.
    if apple_music_app_installed() or not itunes_installed():
        return "folder"
    return "itunes"


def write_m3u8(path, tracks):
    """Fichier de playlist (dans l'ordre), lisible par la plupart des lecteurs."""
    lines = ["#EXTM3U"]
    for track in tracks:
        lines += [f"#EXTINF:-1,{track['artist']} - {track['title']}", track["file"]]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


class ITunes:
    """Pilote iTunes. Les identifiants persistants permettent de retrouver sons et playlists d'une fois sur l'autre."""

    def __init__(self):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()  # nécessaire hors du fil principal
            self.app = win32com.client.Dispatch("iTunes.Application")
        except Exception as exc:
            raise AppleMusicError("Impossible d'ouvrir iTunes. Vérifie qu'il est bien installé.") from exc

    def ids(self, obj):
        return [self.app.ITObjectPersistentIDHigh(obj), self.app.ITObjectPersistentIDLow(obj)]

    def track(self, ids):
        try:
            return self.app.LibraryPlaylist.Tracks.ItemByPersistentID(*ids) if ids else None
        except Exception:
            return None

    def playlist(self, ids):
        try:
            return self.app.LibrarySource.Playlists.ItemByPersistentID(*ids) if ids else None
        except Exception:
            return None

    def create_playlist(self, name):
        return self.app.CreatePlaylist(name)

    def add_file(self, path, playlist=None):
        """Importe un MP3 (dans la playlist si donnée, sinon dans la bibliothèque) et renvoie le son iTunes."""
        target = playlist or self.app.LibraryPlaylist
        status = target.AddFile(str(Path(path).resolve()))
        deadline = time.time() + 120
        while status is not None and status.InProgress and time.time() < deadline:
            time.sleep(0.2)
        tracks = status.Tracks if status is not None else None
        if tracks is None or tracks.Count == 0:
            raise AppleMusicError(f"iTunes n'a pas pu importer {Path(path).name}.")
        return tracks.Item(1)

    def playlist_track_ids(self, playlist):
        """Identifiants des sons déjà dans la playlist (lus une seule fois)."""
        tracks = playlist.Tracks
        return {tuple(self.ids(tracks.Item(i))) for i in range(1, tracks.Count + 1)}

    def add_track(self, playlist, track):
        playlist.AddTrack(track)
