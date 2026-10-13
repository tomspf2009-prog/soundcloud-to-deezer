"""Sans argument : la fenêtre. Avec un lien : la ligne de commande.

`dest` fixe la plateforme de la fenêtre (« deezer » ou « apple ») : c'est ce qui distingue
les deux programmes Windows. Sans `dest`, la fenêtre propose le choix.
"""
import sys


def main(dest=None):
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        sys.exit(cli_main())
    from .gui import main as gui_main
    gui_main(dest)


if __name__ == "__main__":
    main()
