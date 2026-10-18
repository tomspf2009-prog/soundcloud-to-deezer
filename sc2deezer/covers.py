"""Covers personnalisées : n'importe quelle image, recadrée en carré et mise au bon format."""
import hashlib
from io import BytesIO

from PIL import Image, ImageOps


class CoverError(Exception):
    pass


PLAYLIST_SIZE = 1000  # Deezer affiche les covers de playlist jusqu'en 1000x1000
TRACK_SIZE = 800  # intégrée dans le MP3 : nette sur un téléphone, sans alourdir le fichier


def prepare(path, size):
    """Lit une image (JPG, PNG, WEBP…), la redresse, la recadre en carré au centre et la redimensionne.

    Renvoie (octets JPEG, « image/jpeg »), le format accepté partout (Deezer, iTunes, Apple Music).
    """
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)  # photos de téléphone prises de côté
            img = ImageOps.fit(img.convert("RGB"), (size, size), Image.LANCZOS)
    except (OSError, ValueError) as exc:
        raise CoverError("Cette image ne peut pas être lue. Choisis un fichier JPG ou PNG.") from exc
    out = BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue(), "image/jpeg"


def fingerprint(cover):
    """Empreinte d'une cover préparée : sert à ne pas renvoyer deux fois la même."""
    return hashlib.md5(cover[0]).hexdigest()
