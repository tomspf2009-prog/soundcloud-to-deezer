"""Version ligne de commande : sc2deezer <lien de la playlist SoundCloud>."""
import argparse
import getpass
import sys
from pathlib import Path

from . import APP_NAME, REPO_URL, __version__, config, transfer
from .deezer import Deezer, DeezerError

ICONS = {"ok": "✓", "already": "=", "failed": "✗"}


def ask_arl():
    print(f"Colle ta clé Deezer (cookie « arl »). Comment la trouver : {REPO_URL}#trouver-ma-clé-deezer")
    while True:
        arl = config.clean_arl(getpass.getpass("Clé Deezer (rien ne s'affiche quand tu colles, c'est normal) : "))
        if not arl:
            sys.exit("Aucune clé saisie.")
        try:
            dz = Deezer(arl)
        except DeezerError as exc:
            print(exc)
            continue
        config.save(arl=arl, profile_id=None)
        print(f"✓ Clé valide (compte {dz.user_name}), enregistrée dans {config.config_file()}")
        return arl


def pick_profile(arl, wanted, saved_id):
    """Profil Deezer où ajouter les sons : --profil, sinon celui enregistré, sinon on demande."""
    if saved_id and not wanted:
        return saved_id
    dz = Deezer(arl)
    profiles = dz.profiles()
    if wanted:
        for pid, pname in profiles:
            if wanted.casefold() in (pname.casefold(), str(pid)):
                config.save(profile_id=pid)
                return pid
        sys.exit(f"Profil « {wanted} » introuvable. Profils : " + ", ".join(n for _, n in profiles))
    if len(profiles) == 1:
        pid = profiles[0][0]
    else:
        print("Ton offre Deezer a plusieurs profils. Sur lequel ajouter les sons ?")
        for i, (pid, pname) in enumerate(profiles, 1):
            print(f"  {i}. {pname}" + (" (profil principal)" if pid == dz.main_user_id else ""))
        while True:
            choice = input("Numéro du profil : ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(profiles):
                pid = profiles[int(choice) - 1][0]
                break
    config.save(profile_id=pid)
    return pid


def emit(kind, **data):
    if kind == "status":
        print(data["text"])
    elif kind == "connected":
        print(f"Profil Deezer : {data['user']}")
    elif kind == "playlist":
        if data.get("source") == "track":
            print(f"Son SoundCloud : {data['title']}")
        else:
            print(f"Playlist SoundCloud : {data['title']} ({data['total']} sons)")
        print(f"MP3 enregistrés dans : {data['folder']}")
    elif kind == "track":
        line = f"[{data['index']}/{data['total']}] {ICONS[data['status']]} {data['text']}"
        if data.get("detail"):
            line += f" : {data['detail']}"
        print(line, flush=True)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="sc2deezer",
        description=f"{APP_NAME} : copie une playlist SoundCloud dans tes MP3 perso Deezer, avec les covers. "
                    "Sans argument, ouvre la fenêtre.")
    parser.add_argument("url", nargs="?", help="lien SoundCloud : une playlist ou un seul son")
    parser.add_argument("--vers", "--to", dest="dest", choices=["deezer", "apple"], default="deezer",
                        help="où envoyer les sons : deezer (par défaut) ou apple (Apple Music / iTunes)")
    parser.add_argument("--profil", "--profile", dest="profile",
                        help="profil Deezer (offre Famille) où ajouter les sons, par son nom")
    parser.add_argument("--nom", "--name", dest="name", help="nom de la playlist sur Deezer (par défaut : celui de SoundCloud)")
    parser.add_argument("--publique", "--public", dest="public", action="store_true",
                        help="rendre la playlist publique (privée par défaut)")
    parser.add_argument("--coeur", "--like", dest="like", action="store_true", default=None,
                        help="ajouter les sons à tes Coups de cœur (automatique pour un son seul)")
    parser.add_argument("--sans-coeur", "--no-like", dest="like", action="store_false",
                        help="ne pas ajouter un son seul à tes Coups de cœur")
    parser.add_argument("--dossier", "--output", dest="output", type=Path,
                        help=f"dossier des MP3 (par défaut : {config.default_output_dir()})")
    parser.add_argument("--changer-cle", "--set-key", dest="set_key", action="store_true",
                        help="enregistrer une nouvelle clé Deezer")
    parser.add_argument("--oublier-cle", "--forget-key", dest="forget_key", action="store_true",
                        help="effacer la clé Deezer de cet ordinateur")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.forget_key:
        config.forget()
        print("Clé Deezer effacée de cet ordinateur.")
        return 0
    if args.set_key:
        ask_arl()
        if not args.url:
            return 0
    if not args.url:
        parser.error("indique le lien SoundCloud (une playlist ou un seul son)")

    if args.dest == "apple":
        return run_apple(args)

    settings = config.load()
    arl = settings["arl"] or ask_arl()
    try:
        profile_id = pick_profile(arl, args.profile, config.load().get("profile_id"))
        result = transfer.run(args.url, arl, profile_id=profile_id, name=args.name, public=args.public,
                              like=args.like, out_root=args.output, emit=emit)
    except KeyboardInterrupt:
        print("\nArrêté. Relance la même commande pour reprendre là où tu t'es arrêté.")
        return 130
    except DeezerError as exc:
        print(f"Erreur : {exc}\nPour enregistrer une nouvelle clé : sc2deezer --changer-cle")
        return 1
    except Exception as exc:
        print(f"Erreur : {transfer.friendly_error(exc)}")
        return 1

    print()
    if result.kind == "track":
        where = "tes MP3" if args.like is False else "tes MP3 et tes Coups de cœur"
        print(f"✓ Terminé : « {result.title} » est dans {where} (profil {result.profile})")
    else:
        hearts = f", {result.liked} ajouté(s) à tes Coups de cœur" if result.liked else ""
        print(f"✓ Terminé : {result.count} sons dans « {result.title} » (profil {result.profile}){hearts}")
    print(f"  {result.url}")
    if result.failures:
        print(f"{len(result.failures)} élément(s) non copié(s) (relance pour réessayer) :")
        for what, why in result.failures:
            print(f"  ✗ {what} : {why}")
    return 0


def run_apple(args):
    from . import applemusic
    mode = applemusic.detect()
    print("Apple Music :", "import automatique dans iTunes" if mode == "itunes"
          else "préparation d'un dossier à glisser dans l'appli Apple Music")
    try:
        result = transfer.run_apple(args.url, name=args.name, out_root=args.output, emit=emit, mode=mode)
    except KeyboardInterrupt:
        print("\nArrêté. Relance la même commande pour reprendre là où tu t'es arrêté.")
        return 130
    except Exception as exc:
        print(f"Erreur : {transfer.friendly_error(exc)}")
        return 1
    print()
    if mode == "itunes":
        where = "ta bibliothèque iTunes" if result.kind == "track" else f"la playlist « {result.title} » d'iTunes"
        print(f"✓ Terminé : {result.count} son(s) dans {where}")
    elif result.to_import:
        print(f"✓ Prêt : glisse ceci dans l'appli Apple Music, puis laisse-le à cet endroit :\n  {result.to_import}")
    else:
        print("✓ Rien de nouveau : tout a déjà été préparé pour Apple Music.")
    for what, why in result.failures:
        print(f"  ✗ {what} : {why}")
    return 0
