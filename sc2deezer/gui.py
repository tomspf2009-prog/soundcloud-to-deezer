"""La fenêtre : une clé Deezer, un lien SoundCloud, un bouton."""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.font import nametofont

from . import APP_NAME, REPO_URL, __version__, config, transfer
from .deezer import Deezer

ASSETS = Path(__file__).resolve().parent / "assets"
PURPLE, PURPLE_DARK = "#7B2FF7", "#5E1DD1"
GREEN, RED, GREY = "#1E8E3E", "#C5221F", "#5F6368"

ARL_HELP = """\
Ta clé Deezer, c'est quoi ?
C'est un code que Deezer enregistre dans ton navigateur quand tu te connectes \
(un « cookie » appelé arl). Le programme en a besoin pour ajouter les MP3 à ton \
compte, car Deezer ne propose pas d'autre moyen.

Elle reste sur cet ordinateur et n'est envoyée qu'à Deezer. Ne la donne à \
personne : comme un mot de passe, elle permet d'utiliser ton compte.

Comment la trouver (sur ordinateur, avec Chrome, Edge ou Firefox) :
1.  Va sur deezer.com et connecte-toi.
2.  Appuie sur la touche F12. Un panneau s'ouvre : c'est normal, tu ne risques rien.
3.  En haut de ce panneau, clique sur l'onglet « Application » (Chrome, Edge) \
ou « Stockage » (Firefox). Tu ne le vois pas ? Clique sur » au bout des onglets.
4.  À gauche, ouvre « Cookies », puis clique sur https://www.deezer.com.
5.  Tape arl dans la case « Filtrer ».
6.  Double-clique sur la valeur de la ligne arl (une longue suite de lettres et \
de chiffres), puis fais Ctrl+C.
7.  Reviens ici et colle-la avec Ctrl+V (ou clic droit > Coller)."""


def displayable(text):
    """Tk ne sait pas afficher les emojis hors du plan de base : on les retire."""
    return "".join(c for c in str(text) if ord(c) < 0x10000)


def open_path(path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)], check=False)


def add_paste_menu(entry):
    menu = tk.Menu(entry, tearoff=0)
    menu.add_command(label="Coller", command=lambda: entry.event_generate("<<Paste>>"))
    menu.add_command(label="Copier", command=lambda: entry.event_generate("<<Copy>>"))
    menu.add_command(label="Tout effacer", command=lambda: entry.delete(0, "end"))

    def popup(event):
        entry.focus_set()
        menu.tk_popup(event.x_root, event.y_root)
    entry.bind("<Button-3>", popup)


def link(parent, text, command, **kw):
    label = ttk.Label(parent, text=text, foreground=PURPLE, cursor="hand2", style="Link.TLabel", **kw)
    label.bind("<Button-1>", lambda e: command())
    return label


class HintEntry(ttk.Entry):
    """Champ avec un exemple grisé qui disparaît quand on clique dedans."""

    def __init__(self, master, hint, **kw):
        super().__init__(master, **kw)
        self.hint = hint
        self.showing_hint = False
        self.bind("<FocusIn>", self._hide_hint, add="+")
        self.bind("<FocusOut>", self._show_hint, add="+")
        self._show_hint()

    def _show_hint(self, event=None):
        if not super().get():
            self.showing_hint = True
            self.configure(foreground=GREY)
            self.insert(0, self.hint)

    def _hide_hint(self, event=None):
        if self.showing_hint:
            self.showing_hint = False
            self.delete(0, "end")
            self.configure(foreground="black")

    def get(self):
        return "" if self.showing_hint else super().get()


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.arl = ""
        self.worker = None
        self.stop = threading.Event()
        self.result = None

        root.title(APP_NAME)
        try:
            root.iconbitmap(default=str(ASSETS / "icon.ico"))
        except tk.TclError:
            pass
        self._style()
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self._poll)

        settings = config.load()
        self.saved_profile_id = settings.get("profile_id")
        if settings["arl"]:
            self._check_key(settings["arl"], silent=True)
        else:
            self._show_key_form()
        self._fit_to_screen(center=True)

    # ------------------------------------------------------------------ interface

    def _style(self):
        for name in ("TkDefaultFont", "TkTextFont"):
            nametofont(name).configure(family="Segoe UI", size=10)
        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
        style.configure("Sub.TLabel", foreground=GREY)
        style.configure("Hint.TLabel", foreground=GREY, font=("Segoe UI", 9))
        style.configure("Link.TLabel", font=("Segoe UI", 9, "underline"))
        style.configure("Ok.TLabel", foreground=GREEN, font=("Segoe UI Semibold", 10))
        style.configure("Err.TLabel", foreground=RED)
        style.configure("Status.TLabel", font=("Segoe UI Semibold", 10))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI Semibold", 11))

    def _build(self):
        main = ttk.Frame(self.root, padding=(18, 10, 18, 8))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        ttk.Label(main, text="SoundCloud  →  Deezer", style="Title.TLabel").grid(sticky="w")
        ttk.Label(main, text="Copie une playlist SoundCloud dans tes MP3 Deezer, avec les covers d'origine.",
                  style="Sub.TLabel").grid(sticky="w", pady=(0, 8))

        # 1. Compte Deezer
        account = ttk.LabelFrame(main, text=" 1. Ton compte Deezer ", style="Section.TLabelframe", padding=(12, 6, 12, 10))
        account.grid(sticky="ew", pady=(0, 8))
        account.columnconfigure(0, weight=1)

        self.key_form = ttk.Frame(account)
        self.key_form.columnconfigure(0, weight=1)
        ttk.Label(self.key_form, text="Colle ta clé Deezer (le cookie « arl ») :").grid(row=0, column=0, columnspan=2, sticky="w")
        self.key_entry = ttk.Entry(self.key_form, show="•")
        self.key_entry.grid(row=1, column=0, sticky="ew", pady=4)
        self.key_entry.bind("<Return>", lambda e: self._check_key(self.key_entry.get()))
        add_paste_menu(self.key_entry)
        self.key_button = ttk.Button(self.key_form, text="Se connecter",
                                     command=lambda: self._check_key(self.key_entry.get()))
        self.key_button.grid(row=1, column=1, padx=(8, 0))
        info = ttk.Frame(self.key_form)
        info.grid(row=2, column=0, columnspan=2, sticky="w")
        link(info, "Où trouver ma clé ?", self._show_help).pack(side="left")
        ttk.Label(info, text="  ·  Elle reste sur cet ordinateur et n'est envoyée qu'à Deezer.",
                  style="Hint.TLabel").pack(side="left")
        self.key_message = ttk.Label(self.key_form, text="", style="Err.TLabel", wraplength=520)

        self.connected = ttk.Frame(account)
        self.connected.columnconfigure(1, weight=1)
        self.connected_label = ttk.Label(self.connected, text="", style="Ok.TLabel")
        self.connected_label.grid(row=0, column=0, columnspan=2, sticky="w")
        link(self.connected, "Changer de compte", self._forget_key).grid(row=0, column=2, sticky="e")
        self.profile_row = ttk.Frame(self.connected)
        ttk.Label(self.profile_row, text="Ajouter les sons sur le profil :").pack(side="left")
        self.profile_box = ttk.Combobox(self.profile_row, state="readonly", width=28)
        self.profile_box.pack(side="left", padx=(8, 0))
        self.profile_box.bind("<<ComboboxSelected>>", self._on_profile)
        self.profile_hint = ttk.Label(self.connected, style="Hint.TLabel", wraplength=520, text=(
            "Ton offre a plusieurs profils. Les MP3 ajoutés ne pourront être écoutés que sur le "
            "profil choisi : prends le tien."))
        self.profiles = []
        self.profile_id = None

        # 2. Playlist SoundCloud
        source = ttk.LabelFrame(main, text=" 2. Ta playlist SoundCloud ", style="Section.TLabelframe", padding=(12, 6, 12, 10))
        source.grid(sticky="ew", pady=(0, 8))
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Lien :").grid(row=0, column=0, sticky="w")
        self.url_entry = HintEntry(source, "https://soundcloud.com/artiste/sets/ma-playlist")
        self.url_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))
        add_paste_menu(self.url_entry)
        ttk.Label(source, text="Nom :").grid(row=1, column=0, sticky="w")
        self.name_entry = HintEntry(source, "facultatif : sinon le même que sur SoundCloud")
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))
        add_paste_menu(self.name_entry)
        self.public_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(source, text="Rendre la playlist publique (elle est privée par défaut)",
                        variable=self.public_var).grid(row=2, column=0, columnspan=2, sticky="w")

        self.go_button = tk.Button(main, text="Copier vers Deezer", command=self._on_go,
                                   font=("Segoe UI Semibold", 12), fg="white", bg=PURPLE,
                                   activebackground=PURPLE_DARK, activeforeground="white",
                                   disabledforeground="#F4EEFF", relief="flat", cursor="hand2",
                                   padx=20, pady=6, bd=0)
        self.go_button.grid(sticky="ew", pady=(0, 8))

        # 3. Progression
        progress = ttk.LabelFrame(main, text=" 3. Progression ", style="Section.TLabelframe", padding=(12, 6, 12, 10))
        progress.grid(sticky="nsew")
        main.rowconfigure(progress.grid_info()["row"], weight=1)
        progress.columnconfigure(0, weight=1)
        progress.rowconfigure(2, weight=1)
        self.status = ttk.Label(progress, text="Prêt.", style="Status.TLabel", wraplength=520)
        self.status.grid(row=0, column=0, columnspan=2, sticky="w")
        self.bar = ttk.Progressbar(progress, mode="determinate")
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
        self.log = tk.Text(progress, height=5, wrap="word", relief="flat", bg="#F6F6F8",
                           font=("Segoe UI", 9), padx=8, pady=6, state="disabled")
        self.log.grid(row=2, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(progress, command=self.log.yview)
        scroll.grid(row=2, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        self.log.tag_configure("ok", foreground=GREEN)
        self.log.tag_configure("failed", foreground=RED)
        self.log.tag_configure("info", foreground=GREY)

        self.done_buttons = ttk.Frame(progress)
        ttk.Button(self.done_buttons, text="Ouvrir la playlist sur Deezer",
                   command=lambda: webbrowser.open(self.result.playlist_url)).pack(side="left")
        ttk.Button(self.done_buttons, text="Ouvrir le dossier des MP3",
                   command=lambda: open_path(self.result.folder)).pack(side="left", padx=8)

        footer = ttk.Frame(main)
        footer.grid(sticky="ew", pady=(6, 0))
        ttk.Label(footer, text=f"Version {__version__}  ·  gratuit et open source  ·  ",
                  style="Hint.TLabel").pack(side="left")
        link(footer, "aide et code source", lambda: webbrowser.open(REPO_URL)).pack(side="left")

        self._refresh_go()

    def _fit_to_screen(self, center=False):
        """Ajuste la hauteur au contenu sans jamais dépasser l'écran (barre des tâches comprise)."""
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = min(max(self.root.winfo_reqwidth(), self.root.winfo_width() if not center else 0, 640), sw - 40)
        h = min(self.root.winfo_reqheight(), sh - 120)
        self.root.minsize(min(560, w), min(420, h))
        position = f"+{(sw - w) // 2}+{max(10, (sh - 80 - h) // 2)}" if center else ""
        self.root.geometry(f"{w}x{h}{position}")

    def _refresh_go(self):
        running = self.worker is not None and self.worker.is_alive()
        if running:
            self.go_button.configure(text="Arrêter", bg=GREY, activebackground="#4A4D51", state="normal")
        else:
            ready = bool(self.arl and self.profile_id)
            self.go_button.configure(text="Copier vers Deezer", bg=PURPLE if ready else "#CDB8F7",
                                     activebackground=PURPLE_DARK, state="normal" if ready else "disabled")
        for widget in (self.url_entry, self.name_entry):
            widget.configure(state="disabled" if running else "normal")
        self.profile_box.configure(state="disabled" if running else "readonly")

    def _write(self, text, tag="info"):
        self.log.configure(state="normal")
        self.log.insert("end", displayable(text) + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("Trouver ma clé Deezer")
        win.transient(self.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=ARL_HELP, wraplength=520, justify="left").pack(anchor="w")
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text="Ouvrir deezer.com",
                   command=lambda: webbrowser.open("https://www.deezer.com/fr/")).pack(side="left")
        ttk.Button(buttons, text="J'ai compris", command=win.destroy).pack(side="left", padx=(8, 0))
        win.grab_set()

    # ------------------------------------------------------------------ clé Deezer

    def _key_note(self, text, style="Err.TLabel"):
        if text:
            self.key_message.configure(text=text, style=style)
            self.key_message.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        else:
            self.key_message.grid_remove()

    def _show_key_form(self, message=""):
        self.connected.pack_forget()
        self.key_form.pack(fill="x")
        self._key_note(message)
        self.key_button.configure(state="normal")
        self._refresh_go()

    def _check_key(self, raw, silent=False):
        arl = config.clean_arl(raw)
        if not arl:
            self._show_key_form("Colle d'abord ta clé dans le champ ci-dessus.")
            return
        self.key_form.pack(fill="x")
        self.key_button.configure(state="disabled")
        self._key_note("Vérification de la clé…", "Hint.TLabel")
        threading.Thread(target=self._check_key_worker, args=(arl, silent), daemon=True).start()

    def _check_key_worker(self, arl, silent):
        try:
            dz = Deezer(arl)
            self.events.put(("key_ok", {"arl": arl, "main_id": dz.main_user_id, "profiles": dz.profiles()}))
        except Exception as exc:
            text = transfer.friendly_error(exc)
            if silent:
                text = "Ta clé enregistrée ne fonctionne plus. " + text
            self.events.put(("key_bad", {"text": text}))

    def on_key_ok(self, arl, main_id, profiles):
        if arl != config.load()["arl"]:
            config.save(arl=arl, profile_id=None)
            self.saved_profile_id = None
        self.arl = arl
        self.profiles = profiles
        self.key_entry.delete(0, "end")
        self.key_form.pack_forget()
        self.connected.pack(fill="x")
        ids = [pid for pid, _ in profiles]
        if len(profiles) == 1:
            self.profile_id = ids[0]
            self.profile_row.grid_forget()
            self.profile_hint.grid_forget()
            self.connected_label.configure(text=f"✓ Connecté en tant que {displayable(profiles[0][1])}")
        else:
            self.connected_label.configure(text="✓ Clé Deezer valide")
            self.profile_box.configure(values=[displayable(name) + (" (profil principal)" if pid == main_id else "")
                                               for pid, name in profiles])
            self.profile_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
            self.profile_hint.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
            self.profile_id = self.saved_profile_id if self.saved_profile_id in ids else None
            if self.profile_id:
                self.profile_box.current(ids.index(self.profile_id))
            else:
                self.profile_box.set("Choisis ton profil…")
        self._refresh_go()
        self._fit_to_screen()

    def _on_profile(self, event=None):
        self.profile_id = self.profiles[self.profile_box.current()][0]
        self.saved_profile_id = self.profile_id
        config.save(profile_id=self.profile_id)
        self._refresh_go()

    def on_key_bad(self, text):
        self.arl = ""
        self._show_key_form(text)
        self._fit_to_screen()

    def _forget_key(self):
        if self.worker and self.worker.is_alive():
            return
        config.forget()
        self.arl = ""
        self.profile_id = self.saved_profile_id = None
        self._show_key_form()

    # ------------------------------------------------------------------ transfert

    def _on_go(self):
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno(APP_NAME, "Arrêter la copie après le son en cours ?\n\n"
                                   "Rien n'est perdu : relance la même playlist plus tard "
                                   "et elle reprendra là où elle s'est arrêtée."):
                self.stop.set()
                self.status.configure(text="Arrêt après le son en cours…")
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showinfo(APP_NAME, "Colle d'abord le lien de ta playlist SoundCloud.")
            return
        self.stop.clear()
        self.result = None
        self.done_buttons.grid_forget()
        self.bar.configure(value=0, maximum=1)
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.worker = threading.Thread(target=self._transfer_worker, daemon=True, args=(
            url, self.name_entry.get().strip() or None, self.public_var.get()))
        self.worker.start()
        self._refresh_go()

    def _transfer_worker(self, url, name, public):
        emit = lambda kind, **data: self.events.put((kind, data))  # noqa: E731
        try:
            result = transfer.run(url, self.arl, profile_id=self.profile_id, name=name, public=public,
                                  emit=emit, stop=self.stop)
            emit("done", result=result)
        except transfer.Cancelled:
            emit("cancelled")
        except Exception as exc:
            emit("error", text=transfer.friendly_error(exc))

    def on_status(self, text):
        self.status.configure(text=text)

    def on_connected(self, user):
        pass

    def on_playlist(self, title, total, folder):
        self.bar.configure(maximum=total, value=0)
        self._write(f"Playlist « {title} » : {total} sons. MP3 enregistrés dans {folder}")

    def on_progress(self, index, total):
        self.status.configure(text=f"Son {index} sur {total} : téléchargement et envoi sur Deezer…")

    def on_track(self, index, total, text, status, detail=None):
        self.bar.configure(value=index)
        if status == "ok":
            self._write(f"✓ {text}", "ok")
        elif status == "already":
            self._write(f"✓ {text} (déjà sur Deezer)", "ok")
        else:
            self._write(f"✗ {text} : {detail}", "failed")

    def on_done(self, result):
        self.result = result
        self.bar.configure(value=self.bar["maximum"])
        summary = (f"Terminé ! {result.count} sons dans la playlist « {displayable(result.title)} » "
                   f"(profil {displayable(result.profile)}).")
        if result.failures:
            summary += f" {len(result.failures)} élément(s) n'ont pas pu être copiés (détails ci-dessous)."
            self._write("")
            for what, why in result.failures:
                self._write(f"✗ {what} : {why}", "failed")
        self.status.configure(text=summary)
        self.done_buttons.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._refresh_go()
        self._fit_to_screen()

    def on_cancelled(self):
        self.status.configure(text="Copie arrêtée. Relance la même playlist pour reprendre là où tu t'es arrêté.")
        self._refresh_go()

    def on_error(self, text):
        self.status.configure(text="La copie n'a pas pu aboutir.")
        self._write(f"✗ {text}", "failed")
        self._refresh_go()
        messagebox.showerror(APP_NAME, text)

    # ------------------------------------------------------------------ boucle

    def _poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                getattr(self, f"on_{kind}")(**data)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_NAME, "La copie est en cours.\n\nSi tu fermes maintenant, rien n'est "
                                       "perdu : relance la même playlist plus tard et elle reprendra là où "
                                       "elle s'est arrêtée.\n\nFermer quand même ?"):
                return
            self.stop.set()
        self.root.destroy()


def main():
    if sys.platform == "win32":
        try:  # texte net sur les écrans haute résolution
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
