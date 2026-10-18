"""Accès au compte Deezer via l'API interne du site web (la même que deezer.com).

Deezer ne propose pas d'API officielle pour envoyer des MP3 perso : ces appels
reproduisent ce que fait le site quand on utilise « Mes MP3 ».
"""
import json
import random
import re
import time

import requests

GW_URL = "https://www.deezer.com/ajax/gw-light.php"
UPLOAD_URL = "https://upload.deezer.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class DeezerError(Exception):
    pass


# Appels qu'on ne relance pas après une coupure réseau : ils ont pu aboutir côté Deezer,
# et les refaire créerait un doublon (une 2e playlist).
NOT_RETRYABLE = {"playlist.create"}


def with_retries(send, retryable=True, attempts=3):
    """Refait une requête après une coupure réseau passagère (Deezer en coupe parfois)."""
    for attempt in range(attempts):
        try:
            return send()
        except (requests.ConnectionError, requests.Timeout):
            if not retryable or attempt == attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))


class Deezer:
    def __init__(self, arl, profile_id=None):
        """`profile_id` : profil de l'offre Famille à utiliser (par défaut, le profil principal)."""
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.s.cookies.set("arl", arl, domain=".deezer.com")
        self.api_token = "null"
        self._login()
        self.main_user_id = self.user_id
        if profile_id and int(profile_id) != self.user_id:
            self.switch_profile(profile_id)

    def _login(self):
        self.api_token = "null"
        data = self.call("deezer.getUserData", retry=False)
        user = data.get("USER") or {}
        if not user.get("USER_ID"):
            raise DeezerError("Clé Deezer refusée. Elle est peut-être incomplète ou expirée : "
                              "recopie-la depuis deezer.com.")
        self.api_token = data["checkForm"]
        self.sid = data["SESSION_ID"]
        self.referer = data.get("SETTING_REFERER_UPLOAD") or "FR"
        self.user = user
        self.user_id = int(user["USER_ID"])
        self.user_name = user.get("BLOG_NAME") or str(self.user_id)

    def profiles(self):
        """Profils utilisables [(id, nom)]. Les MP3 perso sont propres à chaque profil."""
        multi = self.user.get("MULTI_ACCOUNT") or {}
        if multi.get("ENABLED") and not multi.get("IS_SUB_ACCOUNT"):
            try:
                children = self.call("deezer.getChildAccounts") or []
            except DeezerError:
                children = []
            found = [(int(c["USER_ID"]), c.get("BLOG_NAME") or str(c["USER_ID"])) for c in children
                     if (c.get("EXTRA_FAMILY") or {}).get("IS_LOGGABLE_AS")]
            if found:
                return found
        return [(self.user_id, self.user_name)]

    def switch_profile(self, profile_id):
        """Passe sur un autre profil de l'offre Famille, comme le sélecteur de profil de deezer.com."""
        self.call("user.loginMulti", {"account_id": int(profile_id)})
        try:
            self.call("deezer.userAutolog")
        except DeezerError:
            pass
        self._login()
        if self.user_id != int(profile_id):
            raise DeezerError("Impossible de passer sur ce profil Deezer.")

    def call(self, method, params=None, retry=True):
        r = with_retries(lambda: self.s.post(GW_URL, params={
            "method": method, "input": "3", "api_version": "1.0",
            "api_token": self.api_token, "cid": random.randint(0, 10**9),
        }, json=params or {}, timeout=60), retryable=method not in NOT_RETRYABLE)
        r.raise_for_status()
        data = r.json()
        error = data.get("error")
        if error:
            if retry and "VALID_TOKEN_REQUIRED" in json.dumps(error):
                self._login()
                return self.call(method, params, retry=False)
            raise DeezerError(f"Deezer a refusé « {method} » : {error}")
        return data.get("results")

    def upload(self, path, directory, kind, element_id=0, mime="application/octet-stream"):
        """Même requête que le bouton d'upload de deezer.com."""
        name = re.sub(r"[^\w.\-]", "_", path.name)
        params = {"sid": self.sid, "id": element_id, "resize": 1, "directory": directory,
                  "type": kind, "referer": self.referer, "file": name}

        def send():
            with open(path, "rb") as f:
                return self.s.post(UPLOAD_URL, params=params, files={"file": (name, f, mime)}, timeout=600)
        # Une image remplace la précédente : on peut la renvoyer. Un MP3 renvoyé ferait un doublon.
        r = with_retries(send, retryable=kind == "picture")
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise DeezerError(f"Deezer a refusé l'envoi : {data['error']}")
        return data.get("results")

    def personal_songs(self, tries=3):
        """« Mes MP3 ». Deezer sert parfois une copie en retard de cette liste : on garde la plus récente."""
        freshest = {}
        for _ in range(tries):
            res = self.call("personal_song.getList", {"nb": 2000, "start": 0}) or {}
            if int(res.get("version") or 0) >= int(freshest.get("version") or 0):
                freshest = res
        return freshest.get("data", [])

    def upload_mp3(self, path, timeout=180):
        """Envoie un MP3 dans « Mes MP3 » et renvoie son identifiant une fois traité par Deezer."""
        upload_id = str(self.upload(path, "user", "audio", mime="audio/mpeg"))
        deadline = time.time() + timeout
        while True:
            for song in self.personal_songs(tries=1):
                if upload_id in (str(song.get("UPLOAD_ID")), str(song.get("SNG_ID"))):
                    return int(song["SNG_ID"])
            if time.time() > deadline:
                raise DeezerError("MP3 envoyé, mais Deezer ne l'a pas encore traité. Relance plus tard.")
            time.sleep(3)

    def playlist_exists(self, playlist_id):
        try:
            self.call("deezer.pagePlaylist", {"playlist_id": playlist_id, "lang": "fr", "nb": 1,
                                              "start": 0, "tab": 0, "tags": True, "header": True})
            return True
        except DeezerError:
            return False

    def create_playlist(self, title, description, public):
        return int(self.call("playlist.create", {
            "title": title, "description": description,
            "status": 0 if public else 1, "songs": [],
        }))

    def add_songs(self, playlist_id, sng_ids):
        """Ajoute les sons à la fin de la playlist, dans l'ordre, sans doublons."""
        def add(batch):
            self.call("playlist.addSongs", {"playlist_id": playlist_id,
                                            "songs": [[sng_id, 0] for sng_id in batch], "offset": -1})

        ids = list(dict.fromkeys(sng_ids))
        for i in range(0, len(ids), 50):
            batch = ids[i:i + 50]
            try:
                add(batch)
            except DeezerError as exc:
                if "ERROR_DATA_EXISTS" not in str(exc):
                    raise
                # Deezer refuse tout le lot si un seul son y est déjà (copie interrompue) : un par un.
                for sng_id in batch:
                    try:
                        add([sng_id])
                    except DeezerError as exc:
                        if "ERROR_DATA_EXISTS" not in str(exc):
                            raise

    def set_playlist_cover(self, playlist_id, image_path, mime):
        self.upload(image_path, "playlist", "picture", element_id=playlist_id, mime=mime)

    def like_songs(self, sng_ids):
        """Ajoute des sons aux Coups de cœur (titres likés), comme le bouton ♡ de deezer.com."""
        ids = list(dict.fromkeys(sng_ids))
        for i in range(0, len(ids), 50):
            batch = ids[i:i + 50]
            try:
                self.call("song.addFavorites", {"IDS": batch})
            except DeezerError:
                # Certains comptes n'ont que l'ancienne méthode, un son à la fois.
                for sng_id in batch:
                    self.call("favorite_song.add", {"SNG_ID": sng_id})

    def library_url(self, page):
        """Lien vers une page de la bibliothèque du profil : « loved » (Coups de cœur) ou « personal_song »."""
        return f"https://www.deezer.com/fr/profile/{self.user_id}/{page}"
