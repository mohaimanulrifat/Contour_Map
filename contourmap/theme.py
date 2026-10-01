"""Visual theme: colours and type from the company design (deep indigo, violet accents,
translucent cards, uppercase kickers with a short accent rule, pill buttons, Inter type),
plus the few custom widgets tkinter needs to look like it. No business logic here.
"""
import os
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .branding import resource_path


class C:
    """Palette (hex), taken from the design file."""
    bg = "#161826"            # window
    bg_alt = "#1d1f30"
    card = "#212330"          # translucent card over the window colour
    card_line = "#363845"     # card border
    input = "#171927"         # text fields
    input_line = "#42445c"
    text = "#e9e9ed"
    muted = "#b2b6ca"
    dim = "#7f8399"
    accent = "#9184d9"        # primary accent
    accent_light = "#b5abfc"
    accent_pale = "#d2cefd"
    accent_deep = "#796cbf"
    indigo = "#4c5397"
    indigo_dark = "#353b80"
    plum = "#2b2741"
    ok = "#8fd6a8"
    warn = "#e8c27a"
    err = "#ff8a80"
    pill_line = "#6a6597"     # accent_light at 50 % on the window colour
    disabled_fill = "#2a2c3d"
    disabled_text = "#6a6d80"


_DPI = 1.0


def px(n: float) -> int:
    """Scale a pixel size to the screen's DPI."""
    return max(1, int(round(n * _DPI)))


# ----------------------------------------------------------------------------- fonts
class Fonts:
    family = "Segoe UI"
    mono = "Consolas"


def _load_private_fonts() -> None:
    """Make the bundled Inter files usable by this process only (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        for name in ("Inter-Regular.otf", "Inter-Bold.otf"):
            path = resource_path("assets", "fonts", name)
            if os.path.isfile(path):
                ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0)      # FR_PRIVATE
    except Exception:
        pass


def font(size: int = 10, bold: bool = False) -> tuple:
    return (Fonts.family, size, "bold") if bold else (Fonts.family, size)


def mono(size: int = 9) -> tuple:
    return (Fonts.mono, size)


# ----------------------------------------------------------------------------- setup
def setup(root: tk.Tk) -> None:
    """Call once, right after creating the root window."""
    global _DPI
    try:
        _DPI = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        _DPI = 1.0
    _load_private_fonts()
    families = set(tkfont.families(root))
    for cand in ("Inter", "Segoe UI", "Helvetica Neue", "DejaVu Sans"):
        if cand in families:
            Fonts.family = cand
            break
    for cand in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New"):
        if cand in families:
            Fonts.mono = cand
            break
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        tkfont.nametofont(name).configure(family=Fonts.family, size=10)
    tkfont.nametofont("TkFixedFont").configure(family=Fonts.mono, size=9)

    root.configure(bg=C.bg)
    root.option_add("*TCombobox*Listbox.background", C.input)
    root.option_add("*TCombobox*Listbox.foreground", C.text)
    root.option_add("*TCombobox*Listbox.selectBackground", C.indigo)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", font(10))
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*Font", font(10))
    _style(root)
    install_wheel(root)


def _style(root: tk.Tk) -> None:
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=C.card, foreground=C.text, font=font(10), bordercolor=C.card_line,
                 darkcolor=C.card, lightcolor=C.card, troughcolor=C.input, focuscolor=C.card,
                 selectbackground=C.indigo, selectforeground="#ffffff", insertcolor=C.text)
    st.configure("TFrame", background=C.card)
    st.configure("Bg.TFrame", background=C.bg)
    st.configure("TLabel", background=C.card, foreground=C.text)
    st.configure("Muted.TLabel", foreground=C.muted)
    st.configure("Hint.TLabel", foreground=C.muted, font=font(9))
    st.configure("Field.TLabel", foreground=C.muted, font=font(9))
    st.configure("Bg.TLabel", background=C.bg, foreground=C.text)
    st.configure("BgMuted.TLabel", background=C.bg, foreground=C.muted)
    st.configure("Ok.TLabel", foreground=C.ok, font=font(9))
    st.configure("Bad.TLabel", foreground=C.err, font=font(9))

    field = dict(fieldbackground=C.input, foreground=C.text, bordercolor=C.input_line,
                 lightcolor=C.input, darkcolor=C.input, padding=(8, 5), insertcolor=C.text)
    for name in ("TEntry", "TSpinbox", "TCombobox"):
        st.configure(name, **field)
        st.map(name, bordercolor=[("focus", C.accent), ("disabled", C.card_line)],
               lightcolor=[("focus", C.accent)], darkcolor=[("focus", C.accent)],
               fieldbackground=[("disabled", C.card)], foreground=[("disabled", C.dim)])
    st.configure("TCombobox", arrowcolor=C.accent_light, background=C.input, arrowsize=px(14))
    st.map("TCombobox", fieldbackground=[("readonly", C.input), ("disabled", C.card)],
           selectbackground=[("readonly", C.input)], selectforeground=[("readonly", C.text)],
           background=[("active", C.plum), ("readonly", C.input)],
           arrowcolor=[("disabled", C.dim)])
    st.configure("TSpinbox", arrowcolor=C.accent_light, background=C.input, arrowsize=px(12))
    st.map("TSpinbox", background=[("active", C.plum)])

    for name in ("TCheckbutton", "TRadiobutton"):
        st.configure(name, background=C.card, foreground=C.text, indicatorbackground=C.input,
                     indicatorforeground=C.accent_light, indicatormargin=(0, 0, 6, 0), padding=(2, 3))
        st.map(name, background=[("active", C.card)], foreground=[("disabled", C.dim)],
               indicatorcolor=[("selected", C.accent), ("!selected", C.input)],
               indicatorbackground=[("selected", C.accent), ("!selected", C.input), ("disabled", C.card)],
               indicatorforeground=[("selected", C.bg), ("disabled", C.dim)],
               bordercolor=[("focus", C.accent)])
    _indicators(st, root)
    st.configure("List.TCheckbutton", background=C.input)
    st.map("List.TCheckbutton", background=[("active", C.input)],
           indicatorbackground=[("selected", C.accent), ("!selected", C.card), ("disabled", C.input)],
           indicatorcolor=[("selected", C.accent), ("!selected", C.card)])
    st.configure("TSeparator", background=C.card_line)

    st.configure("TScrollbar", background="#3a3d55", troughcolor=C.card, bordercolor=C.card,
                 arrowcolor=C.muted, relief="flat", gripcount=0, arrowsize=px(11))
    st.map("TScrollbar", background=[("active", C.accent_deep), ("pressed", C.accent)])
    st.configure("Dark.TScrollbar", troughcolor=C.input, bordercolor=C.input, background="#3a3d55")
    st.map("Dark.TScrollbar", background=[("active", C.accent_deep), ("pressed", C.accent)])

    st.configure("Treeview", background=C.input, fieldbackground=C.input, foreground=C.text,
                 rowheight=px(24), bordercolor=C.input, borderwidth=0, relief="flat")
    st.map("Treeview", background=[("selected", C.indigo)], foreground=[("selected", "#ffffff")])
    st.configure("Treeview.Heading", background=C.plum, foreground=C.accent_pale, relief="flat",
                 font=font(9, True), padding=(8, 6), bordercolor=C.plum)
    st.map("Treeview.Heading", background=[("active", C.indigo_dark)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    st.configure("Horizontal.TProgressbar", troughcolor="#2b2d3f", background=C.accent,
                 bordercolor="#2b2d3f", lightcolor=C.accent, darkcolor=C.accent, thickness=px(6))


_IMAGES: list = []        # PhotoImages must stay referenced


def _indicators(st: ttk.Style, root: tk.Tk) -> None:
    """Antialiased checkbox / radio indicators (the stock clam ones are a boxed 'X')."""
    try:
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return
    size = px(18)
    big = size * 6

    gap = px(7)

    def finish(im):
        small = im.resize((size, size), Image.LANCZOS)
        wide = Image.new("RGBA", (size + gap, size), (0, 0, 0, 0))     # transparent gap before the label
        wide.paste(small, (0, 0))
        img = ImageTk.PhotoImage(wide, master=root)
        _IMAGES.append(img)
        return img

    def box(fill, outline, tick=None):
        im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((big * .08, big * .08, big * .92, big * .92), radius=big * .2, fill=fill,
                            outline=outline, width=max(3, big // 14))
        if tick:
            d.line([(big * .27, big * .52), (big * .43, big * .68), (big * .74, big * .33)],
                   fill=tick, width=max(4, big // 8), joint="curve")
        return finish(im)

    def radio(outline, dot=None, fill=C.input):
        im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((big * .08, big * .08, big * .92, big * .92), fill=fill, outline=outline, width=max(3, big // 14))
        if dot:
            d.ellipse((big * .3, big * .3, big * .7, big * .7), fill=dot)
        return finish(im)

    ck = dict(off=box(C.input, C.input_line), hover=box(C.input, C.accent_light),
              on=box(C.accent, C.accent, C.bg), off_dis=box(C.card, C.card_line),
              on_dis=box("#3a3d55", "#3a3d55", C.dim))
    rb = dict(off=radio(C.input_line), hover=radio(C.accent_light), on=radio(C.accent, C.accent),
              off_dis=radio(C.card_line, fill=C.card), on_dis=radio("#3a3d55", C.dim, fill=C.card))
    for name, imgs in (("ck", ck), ("rb", rb)):
        st.element_create(f"{name}.indicator", "image", imgs["off"],
                          ("disabled", "selected", imgs["on_dis"]), ("disabled", imgs["off_dis"]),
                          ("selected", imgs["on"]), ("active", imgs["hover"]), sticky="w")
    for style, el, base in (("TCheckbutton", "ck", "Checkbutton"), ("TRadiobutton", "rb", "Radiobutton")):
        st.layout(style, [(f"{base}.padding", {"sticky": "nswe", "children": [
            (f"{el}.indicator", {"side": "left", "sticky": ""}),
            (f"{base}.focus", {"side": "left", "sticky": "w", "children": [
                (f"{base}.label", {"sticky": "nswe"})]})]})])


# ----------------------------------------------------------------------------- drawing helper
def _round_rect(cv: tk.Canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ----------------------------------------------------------------------------- widgets
class Card(tk.Canvas):
    """Rounded, bordered panel. Put children in `.body`.

    autoheight=True  the card is as tall as its content (use with pack(fill="x"))
    autoheight=False the card fills the space it is given
    """

    def __init__(self, parent, padx=16, pady=14, radius=12, autoheight=True, bg=C.bg):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, height=px(20))
        self._px, self._py, self._r, self._auto = px(padx), px(pady), px(radius), autoheight
        self.body = tk.Frame(self, bg=C.card)
        self._win = self.create_window(self._px, self._py, window=self.body, anchor="nw")
        self.bind("<Configure>", self._on_resize)
        if autoheight:
            self.body.bind("<Configure>", self._on_body)

    def _on_body(self, _e=None):
        h = self.body.winfo_reqheight() + 2 * self._py
        if abs(int(self.cget("height")) - h) > 1:
            self.configure(height=h)

    def _on_resize(self, e):
        self.delete("bg")
        _round_rect(self, 1, 1, e.width - 1, e.height - 1, self._r, fill=C.card, outline=C.card_line,
                    width=1, tags="bg")
        self.tag_lower("bg")
        kw = {"width": max(1, e.width - 2 * self._px)}
        if not self._auto:
            kw["height"] = max(1, e.height - 2 * self._py)
        self.itemconfigure(self._win, **kw)


class PillButton(tk.Canvas):
    """Pill-shaped button. style: primary (filled accent), secondary (outlined), ghost (text)."""

    def __init__(self, parent, text, command=None, style="primary", bg=C.card, padx=22, height=36):
        f = tkfont.Font(family=Fonts.family, size=10, weight="bold")
        self._text, self._cmd, self._style = text, command, style
        w, h = f.measure(text) + 2 * px(padx), px(height)
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._font, self._bw, self._bh = f, w, h
        self._bhover = self._down = False
        self._enabled = True
        self._active = False
        self.bind("<Enter>", lambda e: self._update(hover=True))
        self.bind("<Leave>", lambda e: self._update(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._update(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _update(self, hover=None, down=None):
        if hover is not None:
            self._bhover = hover
        if down is not None:
            self._down = down
        self._draw()

    def _release(self, e):
        was_down = self._down
        self._update(down=False)
        if was_down and self._enabled and 0 <= e.x <= self._bw and 0 <= e.y <= self._bh and self._cmd:
            self._cmd()

    def _colors(self):
        if not self._enabled:
            return C.disabled_fill, C.disabled_fill, C.disabled_text
        if self._style == "primary":
            fill = C.accent_deep if self._down else C.accent_light if self._bhover else C.accent
            return fill, fill, C.bg
        if self._active:
            return C.indigo_dark, C.accent_light, "#ffffff"
        if self._style == "secondary":
            fill = C.plum if (self._bhover or self._down) else self["bg"]
            return fill, (C.accent_light if self._bhover else C.pill_line), C.accent_pale
        return (C.plum if self._bhover else self["bg"]), (C.plum if self._bhover else self["bg"]), C.muted

    def _draw(self):
        self.delete("all")
        fill, line, fg = self._colors()
        _round_rect(self, 1, 1, self._bw - 1, self._bh - 1, self._bh / 2, fill=fill, outline=line, width=1)
        self.create_text(self._bw / 2, self._bh / 2, text=self._text, fill=fg, font=self._font)
        self.configure(cursor="hand2" if self._enabled else "arrow")

    def set_enabled(self, enabled: bool) -> None:
        if enabled != self._enabled:
            self._enabled = enabled
            self._draw()

    def set_active(self, active: bool) -> None:
        """Toggle look (for Pan / Zoom style buttons)."""
        if active != self._active:
            self._active = active
            self._draw()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()


class ProgressBar(tk.Canvas):
    """Slim pill progress bar. Use like ttk.Progressbar: bar["maximum"] = n; bar["value"] = i."""

    def __init__(self, parent, bg=C.bg):
        super().__init__(parent, height=px(6), bg=bg, highlightthickness=0, bd=0)
        self._max, self._value = 1.0, 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def __setitem__(self, key, val):
        if key == "maximum":
            self._max = max(float(val), 1e-9)
        elif key == "value":
            self._value = float(val)
        else:
            return super().__setitem__(key, val)
        self._draw()

    def __getitem__(self, key):
        return {"maximum": self._max, "value": self._value}[key] if key in ("maximum", "value") else super().__getitem__(key)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        _round_rect(self, 0, 0, w, h, h / 2, fill="#2b2d3f", outline="#2b2d3f")
        frac = min(1.0, self._value / self._max)
        if frac > 0:
            _round_rect(self, 0, 0, max(h, w * frac), h, h / 2, fill=C.accent, outline=C.accent)


class TabBar(tk.Frame):
    """Row of kicker-style tabs: '01  DATA' with an accent rule under the active one."""

    def __init__(self, parent, on_select, bg=C.bg):
        super().__init__(parent, bg=bg)
        self._bg, self._on_select = bg, on_select
        self._items = {}
        self.current = None

    def add(self, key: str, number: str, text: str) -> None:
        cell = tk.Frame(self, bg=self._bg, cursor="hand2")
        cell.pack(side="left", padx=(0, px(18)))
        lab = tk.Label(cell, text=(f"{number}  " if number else "") + text.upper(), bg=self._bg, fg=C.muted,
                       font=font(9, True), cursor="hand2")
        lab.pack(anchor="w")
        rule = tk.Frame(cell, bg=self._bg, height=px(2))
        rule.pack(fill="x", pady=(px(5), 0))
        for w in (cell, lab, rule):
            w.bind("<Button-1>", lambda e, k=key: self.select(k))
            w.bind("<Enter>", lambda e, k=key: self._hover(k, True))
            w.bind("<Leave>", lambda e, k=key: self._hover(k, False))
        self._items[key] = (lab, rule)

    def _hover(self, key, on):
        if key != self.current:
            self._items[key][0].config(fg=C.accent_pale if on else C.muted)

    def select(self, key: str) -> None:
        self.current = key
        for k, (lab, rule) in self._items.items():
            active = k == key
            lab.config(fg=C.accent_pale if active else C.muted)
            rule.config(bg=C.accent if active else self._bg)
        self._on_select(key)


class ScrollFrame(tk.Frame):
    """A vertically scrolling area; put children in `.inner`. The scrollbar hides when not needed."""

    def __init__(self, parent, bg=C.card):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

    def _on_scroll(self, lo, hi):
        self.bar.set(lo, hi)
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.bar.pack_forget()
        elif not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y", before=self.canvas)

    def can_scroll(self) -> bool:
        return self.bar.winfo_ismapped()

    def scroll_top(self):
        self.canvas.yview_moveto(0)


def install_wheel(root: tk.Tk) -> None:
    """One mouse-wheel handler for the whole app: scrolls the ScrollFrame under the pointer
    (also over comboboxes / spinboxes, which would otherwise change their value)."""
    def handle(e):
        try:
            w = root.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            return
        step = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
        while w is not None:
            if isinstance(w, ScrollFrame) and w.can_scroll():
                w.canvas.yview_scroll(step, "units")
                return
            w = getattr(w, "master", None)

    for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        root.bind_all(ev, handle)
        for cls in ("TCombobox", "TSpinbox"):
            root.bind_class(cls, ev, lambda e: (handle(e), "break")[1])


def kicker(parent, number: str, text: str, bg=C.card) -> tk.Frame:
    """'▬  01  TITLE' section label: short accent rule, number, uppercase text."""
    row = tk.Frame(parent, bg=bg)
    tk.Frame(row, bg=C.accent, width=px(26), height=px(2)).pack(side="left", padx=(0, px(10)))
    if number:
        tk.Label(row, text=number, bg=bg, fg=C.accent, font=font(9, True)).pack(side="left", padx=(0, px(8)))
    tk.Label(row, text=text.upper(), bg=bg, fg=C.accent_pale, font=font(9, True)).pack(side="left")
    return row


def rounded_image(path: str, height: int, radius_frac: float = 0.18, master=None):
    """A PhotoImage of `path` scaled to `height` px with rounded corners (None if Pillow fails)."""
    try:
        from PIL import Image, ImageDraw, ImageTk
        img = Image.open(path).convert("RGBA")
        w = max(1, int(img.width * height / img.height))
        img = img.resize((w, height), Image.LANCZOS)
        mask = Image.new("L", (w * 4, height * 4), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * 4 - 1, height * 4 - 1),
                                               radius=int(min(w, height) * 4 * radius_frac), fill=255)
        img.putalpha(mask.resize((w, height), Image.LANCZOS))
        return ImageTk.PhotoImage(img, master=master)
    except Exception:
        return None


def gradient_strip(canvas: tk.Canvas, colors) -> None:
    """Draw a horizontal colour ramp (list of hex colours) on `canvas`."""
    canvas.delete("all")
    w, h = int(canvas.cget("width")), int(canvas.cget("height"))
    n = len(colors)
    for i, col in enumerate(colors):
        x1, x2 = i * w / n, (i + 1) * w / n
        canvas.create_rectangle(x1, 0, x2 + 1, h, fill=col, outline=col)
