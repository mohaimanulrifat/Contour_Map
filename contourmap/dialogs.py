"""About window and the text viewer used by the Help menu."""
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from typing import Callable, Optional
from urllib.parse import quote

from . import branding, version
from .theme import C, PillButton, font, mono, px, rounded_image


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


def mailto(subject: str, body: str = "") -> str:
    return f"mailto:{branding.EMAIL}?subject={quote(subject)}" + (f"&body={quote(body)}" if body else "")


def open_folder(path: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)                                 # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def _center_on(win: tk.Toplevel, parent: tk.Misc) -> None:
    win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


class TextViewer(tk.Toplevel):
    """Read-only monospaced text in a window (how to use, terms, licences)."""

    def __init__(self, parent, title: str, text: str, width: int = 760, height: int = 600):
        super().__init__(parent, bg=C.bg)
        self.title(title)
        self.transient(parent)
        self.geometry(f"{px(width)}x{px(height)}")
        self.minsize(px(420), px(300))
        frame = tk.Frame(self, bg=C.input, highlightthickness=1, highlightbackground=C.card_line)
        frame.pack(fill="both", expand=True, padx=px(14), pady=(px(14), px(8)))
        bar = tk.Scrollbar(frame)
        self.text = tk.Text(frame, wrap="word", bg=C.input, fg=C.text, font=mono(10), relief="flat", bd=0,
                            padx=px(14), pady=px(12), highlightthickness=0, insertbackground=C.text,
                            selectbackground=C.indigo, yscrollcommand=bar.set)
        bar.config(command=self.text.yview)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.insert("1.0", text)
        self.text.config(state="disabled")
        row = tk.Frame(self, bg=C.bg)
        row.pack(fill="x", padx=px(14), pady=(0, px(12)))
        PillButton(row, "Close", self.destroy, style="secondary", bg=C.bg).pack(side="right")
        PillButton(row, "Copy all", self._copy, style="ghost", bg=C.bg).pack(side="right", padx=px(8))
        self.bind("<Escape>", lambda e: self.destroy())
        _center_on(self, parent)
        self.focus_set()

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))


class Link(tk.Label):
    """Underlined-on-hover clickable text."""

    def __init__(self, parent, text: str, command: Callable[[], None], bg=C.card, size=10):
        super().__init__(parent, text=text, bg=bg, fg=C.accent_light, cursor="hand2", font=font(size))
        self._f = font(size)
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self.config(font=(self._f[0], self._f[1], "underline"), fg=C.accent_pale))
        self.bind("<Leave>", lambda e: self.config(font=self._f, fg=C.accent_light))


class AboutDialog(tk.Toplevel):
    def __init__(self, parent, on_check_updates: Callable[[], None], on_licences: Callable[[], None],
                 on_terms: Callable[[], None]):
        super().__init__(parent, bg=C.card)
        self.title(f"About {branding.APP_NAME}")
        self.transient(parent)
        self.resizable(False, False)
        self.configure(padx=px(24), pady=px(20))
        self._logo = rounded_image(branding.logo_path(), px(120), master=self) if branding.logo_path() else None

        top = tk.Frame(self, bg=C.card)
        top.pack(fill="x")
        if self._logo:
            tk.Label(top, image=self._logo, bg=C.card).pack(side="left", anchor="n", padx=(0, px(22)))
        head = tk.Frame(top, bg=C.card)
        head.pack(side="left", anchor="n")
        tk.Label(head, text=f"{branding.APP_NAME} {version.VERSION}", bg=C.card, fg=C.text,
                 font=font(17, True)).pack(anchor="w")
        tk.Label(head, text=f"Built: {version.build_date()}", bg=C.card, fg=C.muted, font=font(9)).pack(anchor="w", pady=(2, 8))
        tk.Label(head, text=branding.APP_SUMMARY, bg=C.card, fg=C.text, font=font(10), wraplength=px(380),
                 justify="left").pack(anchor="w")

        self._section("Made by")
        tk.Label(self, text=branding.AUTHOR, bg=C.card, fg=C.text, font=font(10)).pack(anchor="w")
        tk.Label(self, text=branding.AUTHOR_ROLE, bg=C.card, fg=C.muted, font=font(10)).pack(anchor="w")
        links = tk.Frame(self, bg=C.card)
        links.pack(anchor="w", pady=(px(6), 0))
        for i, (text, url) in enumerate((("LinkedIn", branding.LINKEDIN_URL), ("GitHub", branding.GITHUB_PROFILE_URL),
                                         (branding.EMAIL, f"mailto:{branding.EMAIL}"))):
            if i:
                tk.Label(links, text="  ·  ", bg=C.card, fg=C.dim).pack(side="left")
            Link(links, text, lambda u=url: open_url(u)).pack(side="left")
        self._para("Designed by a media professional, not a programmer, and built with the help of an AI "
                   "coding assistant (Claude Code).", top=10)

        self._section("Free to use")
        self._para("Free for personal and commercial use. The maps you make are yours. The app itself may "
                   "not be sold.")
        Link(self, "Read the full terms", on_terms).pack(anchor="w", pady=(px(4), 0))
        self._para("No data collected. The app sends nothing anywhere, except when you click Check for "
                   "updates.", top=10)
        self._para(f"{branding.APP_NAME} includes open-source components, such as Python, matplotlib, SciPy, "
                   "pandas and NumPy, each under its own licence. See Help, Third-party licences.", top=10)

        self._section("Inside this copy")
        tk.Label(self, text="    ".join(f"{k} {v}" for k, v in version.components().items()), bg=C.card,
                 fg=C.muted, font=font(9), wraplength=px(520), justify="left").pack(anchor="w")
        tk.Label(self, text=branding.COPYRIGHT, bg=C.card, fg=C.dim, font=font(9)).pack(anchor="w", pady=(px(12), 0))

        btns = tk.Frame(self, bg=C.card)
        btns.pack(fill="x", pady=(px(16), 0))
        rows = [
            [("Send a suggestion", lambda: open_url(branding.SUGGESTION_URL), "secondary"),
             ("Report a problem", lambda: open_url(branding.PROBLEM_URL), "secondary"),
             ("Check for updates", on_check_updates, "secondary")],
            [("Third-party licences", on_licences, "secondary"),
             ("Copy version info", self._copy_info, "secondary"),
             ("Close", self.destroy, "primary")],
        ]
        self.copy_btn = None
        for r in rows:
            line = tk.Frame(btns, bg=C.card)
            line.pack(fill="x", pady=(0, px(8)))
            for text, cmd, style in r:
                b = PillButton(line, text, cmd, style=style, bg=C.card, padx=16, height=32)
                b.pack(side="left", padx=(0, px(8)))
                if text == "Copy version info":
                    self.copy_btn = b
        self.bind("<Escape>", lambda e: self.destroy())
        _center_on(self, parent)
        self.grab_set()
        self.focus_set()

    def _section(self, text: str):
        tk.Label(self, text=text, bg=C.card, fg=C.text, font=font(10, True)).pack(anchor="w", pady=(px(18), px(3)))

    def _para(self, text: str, top: int = 0):
        tk.Label(self, text=text, bg=C.card, fg=C.text, font=font(10), wraplength=px(520), justify="left").pack(
            anchor="w", pady=(px(top), 0))

    def _copy_info(self):
        self.clipboard_clear()
        self.clipboard_append(version.version_info_text(branding.APP_NAME))
        if self.copy_btn:
            self.copy_btn.set_text("Copied")
            self.after(1500, lambda: self.copy_btn.winfo_exists() and self.copy_btn.set_text("Copy version info"))
