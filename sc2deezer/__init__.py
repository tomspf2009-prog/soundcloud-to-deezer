"""Copie une playlist SoundCloud dans Deezer (MP3 perso + covers d'origine)."""
import truststore

# Utilise les certificats de Windows/macOS : évite les erreurs SSL avec les
# antivirus ou proxys qui inspectent le HTTPS. Doit passer avant tout appel réseau.
truststore.inject_into_ssl()

__version__ = "1.1.0"
APP_NAME = "SoundCloud vers Deezer"
REPO_URL = "https://github.com/tomspf2009-prog/soundcloud-to-deezer"
