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

from . import APP_NAME, REPO_URL, __version__, applemusic, config, soundcloud, transfer
from .deezer import Deezer

ASSETS = Path(__file__).resolve().parent / "assets"
PURPLE, PURPLE_DARK = "#7B2FF7", "#5E1DD1"
# Couleur du gros bouton : violet pour Deezer, rouge-rose (comme son icône) pour Apple Music.
ACCENTS = {"deezer": (PURPLE, PURPLE_DARK, "#CDB8F7"), "apple": ("#E8264A", "#C41C3B", "#F5B5C2")}
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
    def __init__(self, root, dest=None):
        """`dest` : « deezer » ou « apple » pour un programme dédié à une plateforme, None pour le choix."""
        self.root = root
        self.locked = dest
        self.app_name = "SoundCloud vers Apple Music" if dest == "apple" else APP_NAME
        self.events = queue.Queue()
        self.arl = ""
        self.worker = None
        self.stop = threading.Event()
        self.result = None

        root.title(self.app_name)
        try:
            root.iconbitmap(default=str(ASSETS / ("icon-apple.ico" if dest == "apple" else "icon.ico")))
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
        self._on_dest_change(save=False)
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

        target = {"deezer": "Deezer", "apple": "Apple Music"}.get(self.locked, "Deezer · Apple Music")
        ttk.Label(main, text=f"SoundCloud  →  {target}", style="Title.TLabel").grid(sticky="w")
        where = {"deezer": "dans tes MP3 Deezer", "apple": "dans Apple Music"}.get(self.locked, "dans Deezer ou Apple Music")
        ttk.Label(main, text=f"Copie tes sons et playlists SoundCloud {where}, avec les covers d'origine.",
                  style="Sub.TLabel").grid(sticky="w", pady=(0, 8))

        # 1. Destination : compte Deezer, ou Apple Music sur cet ordinateur
        section = {"deezer": " 1. Ton compte Deezer ", "apple": " 1. Apple Music sur cet ordinateur "}
        account = ttk.LabelFrame(main, text=section.get(self.locked, " 1. Où envoyer tes sons ? "),
                                 style="Section.TLabelframe", padding=(12, 6, 12, 10))
        account.grid(sticky="ew", pady=(0, 8))
        account.columnconfigure(0, weight=1)

        self.dest_var = tk.StringVar(value=self.locked or config.load().get("destination") or "deezer")
        if not self.locked:
            choices = ttk.Frame(account)
            choices.pack(fill="x", pady=(0, 6))
            for value, label in (("deezer", "Deezer"), ("apple", "Apple Music")):
                ttk.Radiobutton(choices, text=label, value=value, variable=self.dest_var,
                                command=self._on_dest_change).pack(side="left", padx=(0, 24))

        self.apple_mode = applemusic.detect()
        self.apple_area = ttk.Frame(account)
        if self.apple_mode == "itunes":
            apple_text = "✓ iTunes est installé : les sons et la playlist y seront ajoutés automatiquement."
        else:
            apple_text = ("Le programme prépare un dossier de MP3, avec leurs covers, que tu n'auras "
                          "plus qu'à glisser dans l'appli Apple Music.")
        ttk.Label(self.apple_area, text=apple_text, wraplength=760,
                  style="Ok.TLabel" if self.apple_mode == "itunes" else "TLabel").pack(anchor="w")
        ttk.Label(self.apple_area, style="Hint.TLabel", wraplength=760, text=(
            "Pour les retrouver sur ton iPhone : abonnement Apple Music, avec « Synchroniser la "
            "bibliothèque » activé.")).pack(anchor="w", pady=(4, 0))

        self.deezer_area = ttk.Frame(account)
        self.key_form = ttk.Frame(self.deezer_area)
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

        self.connected = ttk.Frame(self.deezer_area)
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

        # 2. Son ou playlist SoundCloud
        source = ttk.LabelFrame(main, text=" 2. Ton son ou ta playlist SoundCloud ", style="Section.TLabelframe",
                                padding=(12, 6, 12, 10))
        source.grid(sticky="ew", pady=(0, 8))
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="Lien :").grid(row=0, column=0, sticky="w")
        self.url_entry = HintEntry(source, "lien d'un son ou d'une playlist SoundCloud")
        self.url_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))
        add_paste_menu(self.url_entry)
        for sequence in ("<KeyRelease>", "<<Paste>>", "<FocusOut>"):
            self.url_entry.bind(sequence, lambda e: self.root.after(50, self._on_url_change), add="+")
        ttk.Label(source, text="Nom :").grid(row=1, column=0, sticky="w")
        self.name_entry = HintEntry(source, "facultatif : sinon le même que sur SoundCloud")
        self.name_entry.grid(row=1, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))
        add_paste_menu(self.name_entry)
        self.public_var = tk.BooleanVar(value=False)
        self.public_check = ttk.Checkbutton(source, text="Rendre la playlist publique (elle est privée par défaut)",
                                            variable=self.public_var)
        self.public_check.grid(row=2, column=0, columnspan=2, sticky="w")
        self.like_var = tk.BooleanVar(value=False)
        self.like_touched = False
        self.like_check = ttk.Checkbutton(source, text="Ajouter à mes Coups de cœur (titres likés)",
                                          variable=self.like_var, command=self._on_like_click)
        self.like_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.kind = None  # « track » ou « playlist », deviné d'après le lien collé

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
        self.open_button = ttk.Button(self.done_buttons, text="Ouvrir la playlist sur Deezer", command=self._open_result)
        self.open_button.pack(side="left")
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
            target = "Apple Music" if self.apple else "Deezer"
            ready = self.apple or bool(self.arl and self.profile_id)
            self.go_button.configure(text=f"Ajouter à {target}" if self.kind == "track" else f"Copier vers {target}",
                                     bg=self.accent[0] if ready else self.accent[2], activebackground=self.accent[1],
                                     state="normal" if ready else "disabled")
        single = self.kind == "track"
        self.url_entry.configure(state="disabled" if running else "normal")
        self.like_check.configure(state="disabled" if running else "normal")
        self.name_entry.configure(state="disabled" if running or single else "normal")
        # Playlist publique : Deezer uniquement, et sans objet pour un son seul.
        self.public_check.configure(state="disabled" if running or single or self.apple else "normal")
        self.profile_box.configure(state="disabled" if running else "readonly")

    @property
    def apple(self):
        return self.dest_var.get() == "apple"

    @property
    def accent(self):
        """(normal, appuyé, désactivé)"""
        return ACCENTS["apple" if self.apple else "deezer"]

    def _on_dest_change(self, save=True):
        if save and not self.locked:
            config.save(destination=self.dest_var.get())
        if self.apple:  # Coups de cœur et playlist publique : propres à Deezer
            self.deezer_area.pack_forget()
            self.apple_area.pack(fill="x")
            self.like_check.grid_remove()
            self.public_check.grid_remove()
        else:
            self.apple_area.pack_forget()
            self.deezer_area.pack(fill="x")
            self.like_check.grid()
            self.public_check.grid()
        self._refresh_go()
        self._fit_to_screen()

    def _open_result(self):
        result = self.result
        if result.destination == "deezer":
            webbrowser.open(result.url)
        elif result.to_import and result.to_import.is_file() and sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(result.to_import)], check=False)
        else:
            open_path(result.to_import or result.folder)

    def _on_url_change(self):
        kind = soundcloud.guess_kind(self.url_entry.get())
        if kind == self.kind:
            return
        self.kind = kind
        if not self.like_touched:  # un son seul va dans les Coups de cœur, sauf si on a décoché
            self.like_var.set(kind == "track")
        self._refresh_go()

    def _on_like_click(self):
        self.like_touched = True

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
            if messagebox.askyesno(self.app_name, "Arrêter la copie après le son en cours ?\n\n"
                                   "Rien n'est perdu : relance la même playlist plus tard "
                                   "et elle reprendra là où elle s'est arrêtée."):
                self.stop.set()
                self.status.configure(text="Arrêt après le son en cours…")
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showinfo(self.app_name, "Colle d'abord le lien d'un son ou d'une playlist SoundCloud.")
            return
        self._on_url_change()
        self.stop.clear()
        self.result = None
        self.done_buttons.grid_forget()
        self.bar.configure(value=0, maximum=1)
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.worker = threading.Thread(target=self._transfer_worker, daemon=True, args=(
            url, self.name_entry.get().strip() or None, self.public_var.get(), self.like_var.get(), self.apple))
        self.worker.start()
        self._refresh_go()

    def _transfer_worker(self, url, name, public, like, apple):
        emit = lambda kind, **data: self.events.put((kind, data))  # noqa: E731
        try:
            if apple:
                result = transfer.run_apple(url, name=name, emit=emit, stop=self.stop, mode=self.apple_mode)
            else:
                result = transfer.run(url, self.arl, profile_id=self.profile_id, name=name, public=public,
                                      like=like, emit=emit, stop=self.stop)
            emit("done", result=result)
        except transfer.Cancelled:
            emit("cancelled")
        except Exception as exc:
            emit("error", text=transfer.friendly_error(exc))

    def on_status(self, text):
        self.status.configure(text=text)

    def on_connected(self, user):
        pass

    def on_playlist(self, title, total, folder, source="playlist"):
        self.bar.configure(maximum=total, value=0)
        if source == "track":
            self._write(f"Son « {title} ». MP3 enregistré dans {folder}")
        else:
            self._write(f"Playlist « {title} » : {total} sons. MP3 enregistrés dans {folder}")

    def on_progress(self, index, total):
        target = "préparation pour Apple Music" if self.apple else "envoi sur Deezer"
        self.status.configure(text=f"Son {index} sur {total} : téléchargement et {target}…")

    def on_track(self, index, total, text, status, detail=None):
        self.bar.configure(value=index)
        if status == "ok":
            self._write(f"✓ {text}", "ok")
        elif status == "already":
            self._write(f"✓ {text} (déjà fait)", "ok")
        else:
            self._write(f"✗ {text} : {detail}", "failed")

    def _apple_summary(self, result):
        title = displayable(result.title)
        self.open_button.configure(text="Ouvrir le dossier à glisser")
        if result.destination == "itunes":
            self.open_button.pack_forget()
            if result.kind == "track":
                return f"C'est fait ! « {title} » est dans ta bibliothèque iTunes."
            return f"Terminé ! {result.count} sons dans la playlist « {title} » d'iTunes."
        if not result.to_import:
            self.open_button.pack_forget()
            return "Rien de nouveau : tout a déjà été préparé pour Apple Music."
        self._open_result()
        what = "le MP3 sélectionné" if result.kind == "track" else "le dossier qui vient de s'ouvrir"
        return (f"C'est prêt ! Glisse {what} dans l'appli Apple Music, puis laisse-le à cet endroit : "
                "Apple Music y lit les sons.")

    def on_done(self, result):
        self.result = result
        self.bar.configure(value=self.bar["maximum"])
        profile = displayable(result.profile)
        self.open_button.pack(side="left", before=self.done_buttons.winfo_children()[-1])
        if result.destination != "deezer":
            summary = self._apple_summary(result)
        elif result.kind == "track":
            where = "tes MP3 et tes Coups de cœur" if self.like_var.get() else "tes MP3"
            summary = f"C'est fait ! « {displayable(result.title)} » est dans {where} (profil {profile})."
            self.open_button.configure(text="Ouvrir mes Coups de cœur" if self.like_var.get() else "Ouvrir mes MP3")
        else:
            summary = f"Terminé ! {result.count} sons dans la playlist « {displayable(result.title)} » (profil {profile})."
            if result.liked:
                summary += f" {result.liked} ajouté(s) à tes Coups de cœur."
            self.open_button.configure(text="Ouvrir la playlist sur Deezer")
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
        messagebox.showerror(self.app_name, text)

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
            if not messagebox.askyesno(self.app_name, "La copie est en cours.\n\nSi tu fermes maintenant, rien n'est "
                                       "perdu : relance la même playlist plus tard et elle reprendra là où "
                                       "elle s'est arrêtée.\n\nFermer quand même ?"):
                return
            self.stop.set()
        self.root.destroy()


def main(dest=None):
    if sys.platform == "win32":
        try:  # texte net sur les écrans haute résolution
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root, dest)
    root.mainloop()


if __name__ == "__main__":
    main()
