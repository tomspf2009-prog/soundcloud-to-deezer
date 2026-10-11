"""Sans argument : la fenêtre. Avec un lien : la ligne de commande."""
import sys


def main():
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        sys.exit(cli_main())
    from .gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
