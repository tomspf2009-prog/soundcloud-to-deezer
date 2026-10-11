"""Réglages (clé Deezer, profil choisi) et dossiers. Rien ne quitte cet ordinateur."""
import json
import os
import re
from pathlib import Path

ARL_PATTERN = re.compile(r"(?<![0-9a-f])[0-9a-f]{192}(?![0-9a-f])")


def config_dir():
    override = os.environ.get("SC2DEEZER_CONFIG_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    return Path(base) / "soundcloud-to-deezer"


def config_file():
    return config_dir() / "config.json"


def default_output_dir():
    return Path.home() / "Music" / "SoundCloud vers Deezer"


def clean_arl(text):
    """Tolère ce qu'on colle souvent avec la clé : « arl= », guillemets, espaces, lettre en trop."""
    text = (text or "").strip()
    match = ARL_PATTERN.search(text)
    if match:
        return match.group(0)
    text = text.strip("\"' ")
    return text[4:] if text.lower().startswith("arl=") else text


def _read():
    try:
        return json.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load():
    """{"arl": …, "profile_id": …} ; la variable d'environnement DEEZER_ARL a la priorité."""
    settings = _read()
    settings["arl"] = clean_arl(os.environ.get("DEEZER_ARL") or settings.get("arl", ""))
    return settings


def save(**values):
    settings = _read()
    settings.update(values)
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings), encoding="utf-8")


def forget():
    try:
        config_file().unlink()
    except FileNotFoundError:
        pass
