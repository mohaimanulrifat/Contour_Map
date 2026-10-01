"""tkinter front end. Presentation only: all real work lives in the other modules.

Layout: header (name/logo, file) · left: tabs Data / Plot / Labels / Output · right: data preview
and results log · footer: Generate / Cancel / progress.
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

import matplotlib

from . import branding, dialogs, docs, theme, updates, version
from .data_loader import SUPPORTED_EXTS, DataLoadError
from .defaults import COLORMAPS, DEFAULT_OUTPUT, DEFAULT_PLOT
from .engine import FILE_TYPES
from .mapview import MapView
from .runner import SheetResult, build_sheet_figure
from .session import (DPI_CHOICES, DataSession, OptionError, UserOptions, clean_saved,
                      make_run_config, parse_float, parse_int, preview_problem, to_saved, validate)
from .settings import SettingsStore
from .theme import C, Card, PillButton, ProgressBar, ScrollFrame, TabBar, font, kicker, mono, px, rounded_image
from .worker import BatchWorker

EXISTS_LABELS = {"ask": "Ask me", "number": "Add a number: name (1)", "overwrite": "Overwrite"}
INTERP_LABELS = {"linear": "Linear", "cubic": "Cubic (smooth)", "nearest": "Nearest"}
LABEL_KEYS = ("title", "xlabel", "ylabel", "cbar_label")
TABS = (("data", "01", "Data"), ("plot", "02", "Plot"), ("labels", "03", "Labels"), ("output", "04", "Output"))


def _key_of(mapping: Dict[str, str], label: str, default: str) -> str:
    return next((k for k, v in mapping.items() if v == label), default)


class App(tk.Tk):
    def __init__(self, settings: Optional[SettingsStore] = None):
        super().__init__()
        self.title(branding.APP_NAME)
        theme.setup(self)
        self.geometry(f"{px(1260)}x{px(860)}")
        self.minsize(px(1040), px(700))
        self._set_icon()

        self.store = settings or SettingsStore()
        self.session = DataSession()
        self.worker: Optional[BatchWorker] = None
        self.last_output_dir: Optional[str] = None
        self.sheet_vars: Dict[str, tk.BooleanVar] = {}
        self.sheet_checks: List[ttk.Checkbutton] = []
        self._edited = {k: False for k in LABEL_KEYS}      # label box changed by the user?
        self._cols_edited = False                          # X/Y/Z dropdowns changed by the user?
        self._filling = False                              # programmatic fill in progress
        self._logo = None
        self._icon = None
        self._preview_job = None                           # pending debounced map render
        self._preview_tab = "data"
        self._update_q = None
        self._positions = None                             # column indices of the user's X/Y/Z picks

        self._make_vars()
        self._build_header()
        self._build_footer()                               # packed first so it keeps its space
        self._build_body()
        self._apply_saved(self.store.values())
        self._sync_states()
        self._wire_preview()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        try:
            if os.name == "nt":
                self.iconbitmap(branding.resource_path("assets", branding.ICON_FILE))
        except tk.TclError:
            pass
        logo = branding.logo_path()
        if logo:                                           # window icon on other platforms too
            self._icon = rounded_image(logo, 64, master=self)
            if self._icon:
                try:
                    self.iconphoto(True, self._icon)
                except tk.TclError:
                    pass

    # ================================================================== variables
    def _make_vars(self):
        p, o = DEFAULT_PLOT, DEFAULT_OUTPUT
        self.file_var = tk.StringVar(value="No file open")
        self.layout_var = tk.StringVar(value="columns")
        self.header_var = tk.BooleanVar(value=True)
        self.skip_top_var = tk.StringVar(value="0")
        self.skip_bottom_var = tk.StringVar(value="0")
        self.col_vars = [tk.StringVar() for _ in range(3)]
        self.col_status = tk.StringVar()
        self.all_var = tk.BooleanVar(value=True)
        self.preview_var = tk.StringVar()
        self.preview_info = tk.StringVar()
        # plot
        self.interp_var = tk.StringVar(value=INTERP_LABELS[p.interpolation])
        self.res_var = tk.StringVar(value=str(p.grid_resolution))
        self.fill_var = tk.StringVar(value=p.fill_mode)
        self.levmode_var = tk.StringVar(value="number")
        self.levels_var = tk.StringVar(value=str(p.levels))
        self.lmin_var, self.lmax_var, self.lstep_var = (tk.StringVar() for _ in range(3))
        self.cmap_var = tk.StringVar(value=p.cmap)
        self.rev_var = tk.BooleanVar(value=p.reverse_cmap)
        self.flags = {k: tk.BooleanVar(value=v) for k, v in (
            ("show_labels", p.show_labels), ("show_points", p.show_points), ("show_grid", p.show_grid),
            ("show_colorbar", p.show_colorbar), ("equal_aspect", p.equal_aspect),
            ("invert_x", p.invert_x), ("invert_y", p.invert_y), ("mask_hull", p.mask_outside_hull))}
        self.lim_vars = {k: tk.StringVar() for k in ("xmin", "xmax", "ymin", "ymax")}
        self.font_var = tk.StringVar(value="10")
        self.figw_var, self.figh_var = tk.StringVar(value=f"{p.figsize[0]:g}"), tk.StringVar(value=f"{p.figsize[1]:g}")
        # labels
        self.label_vars = {k: tk.StringVar() for k in LABEL_KEYS}
        for k, v in self.label_vars.items():
            v.trace_add("write", lambda *a, key=k: self._label_typed(key))
        # output
        self.out_dir_var = tk.StringVar()
        self.type_var = tk.StringVar(value=o.file_type.upper())
        self.dpi_var = tk.StringVar(value=str(o.dpi))
        self.trans_var = tk.BooleanVar(value=o.transparent)
        self.incl_var = tk.BooleanVar(value=False)
        self.prefix_var, self.suffix_var, self.custom_var = (tk.StringVar() for _ in range(3))
        self.exists_var = tk.StringVar(value=EXISTS_LABELS["ask"])
        self.status_var = tk.StringVar(value="Ready. Open a file to begin.")

    # ================================================================== header / footer
    def _build_header(self):
        bar = tk.Frame(self, bg=C.bg)
        bar.pack(fill="x", padx=px(24), pady=(px(18), px(10)))
        logo = branding.logo_path()
        if logo:
            self._logo = rounded_image(logo, px(48), master=self)
            if self._logo:
                tk.Label(bar, image=self._logo, bg=C.bg).pack(side="left", padx=(0, px(14)))
        names = tk.Frame(bar, bg=C.bg)
        names.pack(side="left")
        tk.Label(names, text=branding.APP_NAME, bg=C.bg, fg=C.text, font=font(16, True)).pack(anchor="w")
        if branding.APP_TAGLINE:
            tk.Label(names, text=branding.APP_TAGLINE, bg=C.bg, fg=C.muted, font=font(10)).pack(anchor="w")
        self.help_btn = PillButton(bar, "Help  ▾", self._open_help_menu, style="secondary", bg=C.bg, padx=18)
        self.help_btn.pack(side="right", padx=(px(10), 0))
        self.open_btn = PillButton(bar, "Open file…", self.open_file, style="primary", bg=C.bg)
        self.open_btn.pack(side="right")
        tk.Label(bar, textvariable=self.file_var, bg=C.bg, fg=C.accent_pale, font=font(10),
                 anchor="e").pack(side="right", padx=px(16))
        self._build_help_menu()

    def _build_footer(self):
        foot = tk.Frame(self, bg=C.bg)
        foot.pack(side="bottom", fill="x", padx=px(24), pady=(px(6), px(18)))
        row = tk.Frame(foot, bg=C.bg)
        row.pack(fill="x")
        self.gen_btn = PillButton(row, "Generate maps", self.generate, style="primary", bg=C.bg, padx=28)
        self.gen_btn.pack(side="left")
        self.cancel_btn = PillButton(row, "Cancel", self.cancel, style="secondary", bg=C.bg)
        self.cancel_btn.pack(side="left", padx=px(10))
        self.folder_btn = PillButton(row, "Open output folder", self._open_output_folder, style="ghost", bg=C.bg)
        if hasattr(os, "startfile"):                       # Windows only
            self.folder_btn.pack(side="left")
        tk.Label(row, textvariable=self.status_var, bg=C.bg, fg=C.muted, font=font(10),
                 anchor="w").pack(side="left", padx=px(14))
        self.progress = ProgressBar(foot)
        self.progress.pack(fill="x", pady=(px(12), 0))
        credits = tk.Frame(foot, bg=C.bg)
        credits.pack(fill="x", pady=(px(10), 0))
        tk.Label(credits, text=f"{branding.title_with_version()}   By {branding.AUTHOR_SHORT}  ·  ",
                 bg=C.bg, fg=C.dim, font=font(9)).pack(side="left")
        dialogs.Link(credits, "About", self._show_about, bg=C.bg, size=9).pack(side="left")

    # ================================================================== body
    def _build_body(self):
        body = tk.Frame(self, bg=C.bg)
        body.pack(fill="both", expand=True, padx=px(24), pady=(0, px(4)))
        body.columnconfigure(0, minsize=px(480), weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        self.tabbar = TabBar(body, self._show_tab)
        self.tabbar.grid(row=0, column=0, sticky="w", pady=(0, px(8)))
        left = Card(body, autoheight=False, padx=14, pady=12)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, px(16)))
        self.scroll = ScrollFrame(left.body)
        self.scroll.pack(fill="both", expand=True)
        self.tab_frames = {}
        for key, num, text in TABS:
            self.tabbar.add(key, num, text)
            self.tab_frames[key] = tk.Frame(self.scroll.inner, bg=C.card)
        self._tab_data(self.tab_frames["data"])
        self._tab_plot(self.tab_frames["plot"])
        self._tab_labels(self.tab_frames["labels"])
        self._tab_output(self.tab_frames["output"])
        self.tabbar.select("data")

        right = tk.Frame(body, bg=C.bg)
        right.grid(row=0, column=1, rowspan=2, sticky="nsew")
        right.rowconfigure(0, weight=5)
        right.rowconfigure(1, weight=2)
        right.columnconfigure(0, weight=1)
        self._build_preview(right)
        self._build_log(right)

    def _show_tab(self, key):
        for k, f in self.tab_frames.items():
            f.pack_forget()
        self.tab_frames[key].pack(fill="both", expand=True)
        self.scroll.scroll_top()

    # ---- small builders
    def _group(self, parent, text, first=False):
        ttk.Label(parent, text=text, font=font(10, True), foreground=C.accent_pale).pack(
            anchor="w", pady=(0 if first else px(16), px(6)))

    def _hint(self, parent, text, wrap=420):
        lab = ttk.Label(parent, text=text, style="Hint.TLabel", wraplength=px(wrap), justify="left")
        lab.pack(anchor="w", pady=(px(2), 0))
        return lab

    def _row(self, parent, pady=2):
        r = tk.Frame(parent, bg=C.card)
        r.pack(fill="x", pady=pady)
        return r

    def _labeled(self, parent, text, widget_factory, label_w=15):
        r = self._row(parent)
        ttk.Label(r, text=text, style="Field.TLabel", width=label_w).pack(side="left")
        w = widget_factory(r)
        return r, w

    def _spin(self, parent, var, lo, hi, width=7, inc=1, command=None):
        sp = ttk.Spinbox(parent, textvariable=var, from_=lo, to=hi, increment=inc, width=width,
                         command=command)
        if command:
            sp.bind("<Return>", lambda e: command())
            sp.bind("<FocusOut>", lambda e: command())
        return sp

    # ---- tab 01: data
    def _tab_data(self, t):
        self._group(t, "Layout", first=True)
        ttk.Radiobutton(t, text="Column format (X, Y, Z columns)", value="columns",
                        variable=self.layout_var, command=self._on_reading_change).pack(anchor="w")
        ttk.Radiobutton(t, text="Grid / matrix format", value="grid", variable=self.layout_var,
                        command=self._on_reading_change).pack(anchor="w")
        self._hint(t, "Grid format: row headers = Y, column headers = X, cells = Z.")
        self.header_check = ttk.Checkbutton(t, text="Use first row as column titles",
                                            variable=self.header_var, command=self._on_reading_change)
        self.header_check.pack(anchor="w", pady=(px(10), 0))
        self._labeled(t, "Skip rows at top", lambda r: self._spin(
            r, self.skip_top_var, 0, 9999, command=self._on_reading_change).pack(side="left"), 20)
        self._labeled(t, "Ignore rows at bottom", lambda r: self._spin(
            r, self.skip_bottom_var, 0, 9999, command=self._on_reading_change).pack(side="left"), 20)

        self._group(t, "Columns")
        self.col_boxes = []
        for i, name in enumerate("XYZ"):
            def make(r, i=i):
                cb = ttk.Combobox(r, textvariable=self.col_vars[i], state="readonly", width=30)
                cb.pack(side="left", fill="x", expand=True)
                cb.bind("<<ComboboxSelected>>", lambda e: self._on_column_pick())
                self.col_boxes.append(cb)
            self._labeled(t, f"{name} axis", make, 8)
        self.col_status_label = ttk.Label(t, textvariable=self.col_status, style="Hint.TLabel",
                                          wraplength=px(420), justify="left")
        self.col_status_label.pack(anchor="w", pady=(px(4), 0))

        self._group(t, "Sheets to process")
        self.all_check = ttk.Checkbutton(t, text="Process all sheets", variable=self.all_var,
                                         command=self._on_all_toggle)
        self.all_check.pack(anchor="w")
        box = tk.Frame(t, bg=C.input_line)
        box.pack(fill="x", pady=(px(6), 0))
        self.sheet_scroll = ScrollFrame(box, bg=C.input)
        self.sheet_scroll.canvas.configure(height=px(130))
        self.sheet_scroll.pack(fill="x", padx=1, pady=1)

    # ---- tab 02: plot
    def _tab_plot(self, t):
        self._group(t, "Interpolation", first=True)
        self._labeled(t, "Method", lambda r: ttk.Combobox(
            r, textvariable=self.interp_var, state="readonly", width=18,
            values=list(INTERP_LABELS.values())).pack(side="left"), 16)
        self._labeled(t, "Grid resolution", lambda r: self._spin(
            r, self.res_var, 10, 2000, width=7, inc=10).pack(side="left"), 16)
        ttk.Checkbutton(t, text="Mask outside the data hull", variable=self.flags["mask_hull"]).pack(anchor="w", pady=(px(4), 0))

        self._group(t, "Contours")
        r = self._row(t)
        for text, val in (("Filled", "filled"), ("Lines", "lines"), ("Both", "both")):
            ttk.Radiobutton(r, text=text, value=val, variable=self.fill_var).pack(side="left", padx=(0, px(14)))
        r = self._row(t, pady=4)
        ttk.Radiobutton(r, text="Number of levels", value="number", variable=self.levmode_var,
                        command=self._sync_states).pack(side="left")
        self.levels_spin = self._spin(r, self.levels_var, 2, 100, width=6)
        self.levels_spin.pack(side="left", padx=px(10))
        r = self._row(t)
        ttk.Radiobutton(r, text="Custom", value="custom", variable=self.levmode_var,
                        command=self._sync_states).pack(side="left")
        self.custom_entries = []
        for text, var in (("min", self.lmin_var), ("max", self.lmax_var), ("step", self.lstep_var)):
            ttk.Label(r, text=text, style="Field.TLabel").pack(side="left", padx=(px(10), px(3)))
            e = ttk.Entry(r, textvariable=var, width=6)
            e.pack(side="left")
            self.custom_entries.append(e)

        self._group(t, "Colours")
        r = self._row(t)
        self.cmap_box = ttk.Combobox(r, textvariable=self.cmap_var, state="readonly", width=16, values=COLORMAPS)
        self.cmap_box.pack(side="left")
        self.cmap_box.bind("<<ComboboxSelected>>", lambda e: self._draw_cmap())
        self.cmap_strip = tk.Canvas(r, width=px(110), height=px(14), highlightthickness=0, bg=C.card)
        self.cmap_strip.pack(side="left", padx=px(10))
        ttk.Checkbutton(t, text="Reverse colormap", variable=self.rev_var, command=self._draw_cmap).pack(anchor="w", pady=(px(4), 0))

        self._group(t, "Show")
        grid = tk.Frame(t, bg=C.card)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="a")
        items = (("Contour labels", "show_labels"), ("Data points", "show_points"),
                 ("Grid lines", "show_grid"), ("Colorbar", "show_colorbar"),
                 ("Equal aspect ratio", "equal_aspect"), ("Invert X axis", "invert_x"),
                 ("Invert Y axis", "invert_y"))
        for i, (text, key) in enumerate(items):
            ttk.Checkbutton(grid, text=text, variable=self.flags[key]).grid(row=i // 2, column=i % 2, sticky="w")

        self._group(t, "Axis limits (empty = automatic)")
        for name, lo, hi in (("X", "xmin", "xmax"), ("Y", "ymin", "ymax")):
            r = self._row(t)
            ttk.Label(r, text=name, style="Field.TLabel", width=3).pack(side="left")
            for key, lab in ((lo, "min"), (hi, "max")):
                ttk.Label(r, text=lab, style="Field.TLabel").pack(side="left", padx=(px(6), px(3)))
                ttk.Entry(r, textvariable=self.lim_vars[key], width=9).pack(side="left")

        self._group(t, "Size and text")
        self._labeled(t, "Font size", lambda r: self._spin(r, self.font_var, 4, 40, width=6).pack(side="left"), 16)

        def figsize(r):
            self._spin(r, self.figw_var, 2, 40, width=6, inc=0.5).pack(side="left")
            ttk.Label(r, text="×", style="Field.TLabel").pack(side="left", padx=px(6))
            self._spin(r, self.figh_var, 2, 40, width=6, inc=0.5).pack(side="left")
            ttk.Label(r, text="inches", style="Field.TLabel").pack(side="left", padx=px(8))
        self._labeled(t, "Figure size", figsize, 16)
        self._draw_cmap()

    # ---- tab 03: labels
    def _tab_labels(self, t):
        self._hint(t, "Pre-filled from the column titles. Edit a box to override it; boxes you "
                      "don't touch follow each sheet's own titles.")
        for key, text in (("title", "Plot title"), ("xlabel", "X axis name"),
                          ("ylabel", "Y axis name"), ("cbar_label", "Colorbar label")):
            ttk.Label(t, text=text, style="Field.TLabel").pack(anchor="w", pady=(px(12), px(3)))
            ttk.Entry(t, textvariable=self.label_vars[key]).pack(fill="x")
        PillButton(t, "Reset to column titles", self._reset_labels, style="secondary", height=32).pack(anchor="w", pady=(px(16), 0))

    # ---- tab 04: output
    def _tab_output(self, t):
        self._group(t, "Folder", first=True)
        r = self._row(t)
        ttk.Entry(r, textvariable=self.out_dir_var).pack(side="left", fill="x", expand=True)
        PillButton(r, "Browse…", self._browse_out, style="secondary", height=32, padx=16).pack(side="left", padx=(px(8), 0))

        self._group(t, "Image")
        r = self._row(t)
        self.type_box = ttk.Combobox(r, textvariable=self.type_var, state="readonly", width=7,
                                     values=[f.upper() for f in FILE_TYPES])
        self.type_box.pack(side="left")
        self.type_box.bind("<<ComboboxSelected>>", lambda e: self._sync_states())
        ttk.Label(r, text="DPI", style="Field.TLabel").pack(side="left", padx=(px(16), px(6)))
        ttk.Combobox(r, textvariable=self.dpi_var, state="readonly", width=6,
                     values=[str(d) for d in DPI_CHOICES]).pack(side="left")
        self.trans_check = ttk.Checkbutton(t, text="Transparent background", variable=self.trans_var)
        self.trans_check.pack(anchor="w", pady=(px(8), 0))

        self._group(t, "File names")
        self._hint(t, "By default each image is named after its sheet.")
        ttk.Checkbutton(t, text="Put the data file name before the sheet name", variable=self.incl_var).pack(anchor="w", pady=(px(6), 0))
        self._labeled(t, "Prefix", lambda r: ttk.Entry(r, textvariable=self.prefix_var).pack(side="left", fill="x", expand=True), 13)
        self._labeled(t, "Suffix", lambda r: ttk.Entry(r, textvariable=self.suffix_var).pack(side="left", fill="x", expand=True), 13)
        _, self.custom_entry = self._labeled(
            t, "Custom name", lambda r: (lambda e: (e.pack(side="left", fill="x", expand=True), e)[1])(
                ttk.Entry(r, textvariable=self.custom_var)), 13)
        self.custom_hint = self._hint(t, "")
        self._labeled(t, "If the file exists", lambda r: ttk.Combobox(
            r, textvariable=self.exists_var, state="readonly", width=22,
            values=list(EXISTS_LABELS.values())).pack(side="left"), 13)

    # ---- right column
    def _build_preview(self, parent):
        card = Card(parent, autoheight=False, padx=14, pady=12)
        card.grid(row=0, column=0, sticky="nsew", pady=(0, px(12)))
        top = tk.Frame(card.body, bg=C.card)
        top.pack(fill="x", pady=(0, px(8)))
        self.ptabs = TabBar(top, self._show_preview_tab, bg=C.card)
        self.ptabs.add("data", "", "Data preview")
        self.ptabs.add("map", "", "Map preview")
        self.ptabs.pack(side="left")
        self.preview_box = ttk.Combobox(top, textvariable=self.preview_var, state="readonly", width=26)
        self.preview_box.pack(side="right")
        self.preview_box.bind("<<ComboboxSelected>>", lambda e: self._on_preview_sheet())
        ttk.Label(top, text="Sheet", style="Field.TLabel").pack(side="right", padx=(0, px(8)))

        self.data_frame = tk.Frame(card.body, bg=C.card)
        ttk.Label(self.data_frame, textvariable=self.preview_info, style="Hint.TLabel").pack(anchor="w", pady=(0, px(6)))
        grid = tk.Frame(self.data_frame, bg=C.card)
        grid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(grid, show="headings", height=6)
        vs = ttk.Scrollbar(grid, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.tag_configure("odd", background="#1b1d2d")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        grid.rowconfigure(0, weight=1)
        grid.columnconfigure(0, weight=1)

        self.mapview = MapView(card.body)
        self.mapview.show_message("Open a file to see a map preview.")
        self.ptabs.select("data")

    # ---- live map preview
    def _show_preview_tab(self, key):
        self._preview_tab = key
        self.data_frame.pack_forget()
        self.mapview.pack_forget()
        if key == "map":
            self.mapview.pack(fill="both", expand=True)
            self._schedule_preview(now=True)
        else:
            self.data_frame.pack(fill="both", expand=True)

    def _wire_preview(self):
        """Redraw the map (debounced) whenever anything that affects it changes."""
        vars_ = [self.layout_var, self.header_var, self.skip_top_var, self.skip_bottom_var, *self.col_vars,
                 self.interp_var, self.res_var, self.fill_var, self.levmode_var, self.levels_var,
                 self.lmin_var, self.lmax_var, self.lstep_var, self.cmap_var, self.rev_var,
                 *self.flags.values(), *self.lim_vars.values(), self.font_var, self.figw_var,
                 self.figh_var, *self.label_vars.values()]
        for v in vars_:
            v.trace_add("write", lambda *a: self._schedule_preview())

    def _schedule_preview(self, now: bool = False):
        if self._preview_tab != "map":
            return
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(0 if now else 450, self._render_preview)

    def _render_preview(self):
        self._preview_job = None
        if self._preview_tab != "map":
            return
        if not self.session.is_open:
            self.mapview.show_message("Open a file to see a map preview.")
            return
        sheet = self.preview_var.get()
        try:
            self._read_reading()
            opts = self._collect_options()
            problem = preview_problem(opts)
            if problem:
                raise OptionError(problem)
            cfg = make_run_config(self.session, opts)
            df = self.session.frame(sheet)
        except OptionError as e:
            self.mapview.show_message(str(e), "error")
            return
        except DataLoadError as e:
            self.mapview.show_message(str(e), "error")
            return

        def build():
            result, data, _cols, note = build_sheet_figure(df, cfg)
            info = [data.summary()] + ([note] if note else []) + result.grid.notes
            return result.figure, "  ·  ".join(info)
        self.mapview.request(build)

    def _build_log(self, parent):
        card = Card(parent, autoheight=False, padx=14, pady=12)
        card.grid(row=1, column=0, sticky="nsew")
        kicker(card.body, "", "Results").pack(anchor="w", pady=(0, px(8)))
        frame = tk.Frame(card.body, bg=C.input)
        frame.pack(fill="both", expand=True)
        self.log = tk.Text(frame, height=6, state="disabled", wrap="word", bg=C.input, fg=C.text,
                           font=mono(9), relief="flat", bd=0, padx=10, pady=8, highlightthickness=0,
                           insertbackground=C.text, selectbackground=C.indigo)
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        for tag, col in (("ok", C.ok), ("skip", C.warn), ("err", C.err), ("info", C.muted)):
            self.log.tag_config(tag, foreground=col)

    # ================================================================== state sync
    def _sync_states(self):
        busy = self.worker is not None and self.worker.running
        grid = self.layout_var.get() == "grid"
        is_open = self.session.is_open
        self.gen_btn.set_enabled(is_open and not busy)
        self.cancel_btn.set_enabled(busy)
        self.open_btn.set_enabled(not busy)
        self.folder_btn.set_enabled(bool(self.last_output_dir) and not busy)
        # data tab
        self.header_check.state(["disabled"] if grid else ["!disabled"])
        for cb in self.col_boxes:
            cb.config(state="disabled" if grid or not is_open else "readonly")
        # plot tab
        number = self.levmode_var.get() == "number"
        self.levels_spin.state(["!disabled"] if number else ["disabled"])
        for e in self.custom_entries:
            e.state(["disabled"] if number else ["!disabled"])
        # output tab
        jpg = self.type_var.get() == "JPG"
        if jpg:
            self.trans_var.set(False)
        self.trans_check.state(["disabled"] if jpg else ["!disabled"])
        self._sync_sheet_state()

    def _single_sheet(self) -> bool:
        return sum(v.get() for v in self.sheet_vars.values()) == 1

    def _sync_sheet_state(self):
        for cb in self.sheet_checks:
            cb.state(["disabled"] if self.all_var.get() else ["!disabled"])
        one = self._single_sheet()
        self.custom_entry.config(state="normal" if one else "disabled")
        self.custom_hint.config(text="" if one else "Custom name is available when a single sheet is processed.")

    def _draw_cmap(self):
        try:
            cmap = matplotlib.colormaps[self.cmap_var.get() + ("_r" if self.rev_var.get() else "")]
        except KeyError:
            return
        theme.gradient_strip(self.cmap_strip, [matplotlib.colors.to_hex(cmap(i / 59)) for i in range(60)])

    # ================================================================== file + preview
    def open_file(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTS)
        start = self.store.get("last_open_dir")
        path = filedialog.askopenfilename(
            title="Select a data file", initialdir=start if start and os.path.isdir(start) else None,
            filetypes=[("Data files", exts), ("All files", "*.*")])
        if not path:
            return
        try:
            self._read_reading()                           # sync header/skip/layout into the session
            self.session.open(path)
        except OptionError as e:
            messagebox.showwarning("Data options", str(e))
            return
        except DataLoadError as e:
            messagebox.showerror("Cannot open file", str(e))
            return
        self.store.set("last_open_dir", os.path.dirname(path))
        self.file_var.set(f"{os.path.basename(path)}  ·  {len(self.session.sheets)} sheet(s)")
        if not self.out_dir_var.get() or not os.path.isdir(self.out_dir_var.get()):
            self.out_dir_var.set(os.path.dirname(path))
        self._log(f"Loaded {os.path.basename(path)}: {len(self.session.sheets)} sheet(s)", "info")
        self.status_var.set("File loaded. Check the preview, then Generate.")
        self._build_sheet_list()
        self.preview_box.config(values=self.session.sheets)
        self.preview_var.set(self.session.sheets[0])
        self._cols_edited = False
        self._edited = {k: False for k in LABEL_KEYS}
        self._refresh_preview()
        self._sync_states()

    def _read_reading(self):
        """Push the Data-tab reading options into the session. Raises OptionError if invalid."""
        top = parse_int(self.skip_top_var.get(), "Skip rows at top", 0, 100000)
        bottom = parse_int(self.skip_bottom_var.get(), "Ignore rows at bottom", 0, 100000)
        self.session.set_reading(self.header_var.get(), top, bottom, self.layout_var.get())

    def _on_reading_change(self):
        self._sync_states()
        if not self.session.is_open:
            return
        try:
            self._read_reading()
        except OptionError:
            return                                          # half-typed number; wait for a valid one
        self._refresh_preview()

    def _on_preview_sheet(self):
        self._refresh_preview()

    def _refresh_preview(self):
        sheet = self.preview_var.get()
        self.tree.delete(*self.tree.get_children())
        if not self.session.is_open or not sheet:
            self.tree["columns"] = ()
            self.preview_info.set("")
            return
        try:
            cols, rows, total = self.session.preview(sheet)
        except DataLoadError as e:
            self.tree["columns"] = ()
            self.preview_info.set("")
            messagebox.showerror("Cannot read sheet", str(e))
            return
        ids = [f"c{i}" for i in range(len(cols))]
        self.tree["columns"] = ids
        for i, (cid, title) in enumerate(zip(ids, cols)):
            longest = max([len(title)] + [len(r[i]) for r in rows])
            self.tree.heading(cid, text=title)
            self.tree.column(cid, width=max(70, min(260, longest * 8 + 22)), stretch=False, anchor="w")
        for n, r in enumerate(rows):
            self.tree.insert("", "end", values=r, tags=("odd",) if n % 2 else ())
        self.preview_info.set(f"first {len(rows)} of {total} rows · {len(cols)} columns")
        self._update_columns(sheet)
        self._prefill_labels()
        self._schedule_preview()

    # ================================================================== columns
    def _update_columns(self, sheet):
        """Fill the X/Y/Z dropdowns for the previewed sheet and show the data check."""
        grid = self.layout_var.get() == "grid"
        names = [] if grid else self.session.column_names(sheet)
        for cb in self.col_boxes:
            cb.config(values=names)
        self._filling = True
        try:
            if grid:
                for v, n in zip(self.col_vars, "XYZ"):
                    v.set(f"{n} (from grid)")
            elif not self._cols_edited:
                for v, c in zip(self.col_vars, self.session.guess_columns(sheet)):
                    v.set(c or "")
            else:                                            # keep picks; same position if name is absent
                old = [v.get() for v in self.col_vars]
                pos = getattr(self, "_positions", None) or (0, 1, 2)
                for i, v in enumerate(self.col_vars):
                    v.set(old[i] if old[i] in names else (names[pos[i]] if pos[i] < len(names) else ""))
        finally:
            self._filling = False
        self._update_check(sheet)

    def _chosen_columns(self):
        if self.layout_var.get() == "grid" or not self._cols_edited:
            return None, None
        cols = tuple(v.get() for v in self.col_vars)
        if not all(cols):
            return None, None
        names = self.session.column_names(self.preview_var.get()) if self.session.is_open else []
        pos = tuple(names.index(c) for c in cols) if all(c in names for c in cols) else None
        return cols, pos

    def _on_column_pick(self):
        self._cols_edited = True
        _, pos = self._chosen_columns()
        self._positions = pos
        self._update_check(self.preview_var.get())
        self._prefill_labels()

    def _update_check(self, sheet):
        label = self.col_status_label
        if not self.session.is_open:
            self.col_status.set("")
            return
        if self.layout_var.get() == "grid":
            ok, text = self.session.check(sheet)
            self.col_status.set(f"Grid: first row = X, first column = Y, cells = Z.  {text}")
        else:
            cols, pos = self._chosen_columns()
            if cols and len(set(cols)) < 3:
                ok, text = False, "X, Y and Z must be three different columns."
            else:
                ok, text = self.session.check(sheet, cols, pos)
            self.col_status.set(text)
        label.config(style="Ok.TLabel" if ok else "Bad.TLabel")

    # ================================================================== sheet checklist
    def _build_sheet_list(self):
        for w in self.sheet_scroll.inner.winfo_children():
            w.destroy()
        self.sheet_vars, self.sheet_checks = {}, []
        for name in self.session.sheets:
            var = tk.BooleanVar(value=True)
            row = tk.Frame(self.sheet_scroll.inner, bg=C.input)
            row.pack(fill="x", padx=6)
            cb = ttk.Checkbutton(row, text=name, variable=var, command=self._on_sheet_toggle, style="List.TCheckbutton")
            cb.pack(anchor="w")
            self.sheet_vars[name] = var
            self.sheet_checks.append(cb)
        self.all_var.set(True)
        self._sync_sheet_state()

    def _on_all_toggle(self):
        if self.all_var.get():
            for v in self.sheet_vars.values():
                v.set(True)
        self._sync_sheet_state()

    def _on_sheet_toggle(self):
        self.all_var.set(all(v.get() for v in self.sheet_vars.values()))
        self._sync_sheet_state()

    # ================================================================== labels
    def _label_typed(self, key):
        if not self._filling:
            self._edited[key] = True

    def _prefill_labels(self):
        if not self.session.is_open:
            return
        sheet = self.preview_var.get()
        cols, _ = self._chosen_columns()
        try:
            texts = self.session.default_labels(sheet, cols)
        except DataLoadError:
            return
        self._filling = True
        try:
            for k in LABEL_KEYS:
                if not self._edited[k]:
                    self.label_vars[k].set(texts[k])
        finally:
            self._filling = False

    def _reset_labels(self):
        self._edited = {k: False for k in LABEL_KEYS}
        self._prefill_labels()

    def _browse_out(self):
        start = self.out_dir_var.get()
        d = filedialog.askdirectory(title="Output folder", initialdir=start if os.path.isdir(start) else None)
        if d:
            self.out_dir_var.set(os.path.normpath(d))

    # ================================================================== options <-> widgets
    def _limits(self, lo, hi, name):
        a = parse_float(self.lim_vars[lo].get(), f"{name} axis min", blank_ok=True)
        b = parse_float(self.lim_vars[hi].get(), f"{name} axis max", blank_ok=True)
        if (a is None) != (b is None):
            raise OptionError(f"{name} axis limits: fill in both min and max, or leave both empty.")
        return None if a is None else (a, b)

    def _collect_options(self) -> UserOptions:
        """Read every widget into a typed UserOptions. Raises OptionError with a friendly message."""
        top = parse_int(self.skip_top_var.get(), "Skip rows at top", 0, 100000)
        bottom = parse_int(self.skip_bottom_var.get(), "Ignore rows at bottom", 0, 100000)
        custom = self.levmode_var.get() == "custom"
        fs = parse_float(self.font_var.get(), "Font size", blank_ok=True)
        if fs is not None and not 4 <= fs <= 40:
            raise OptionError("Font size: must be between 4 and 40.")
        figw, figh = (parse_float(v.get(), n) for v, n in ((self.figw_var, "Figure width"), (self.figh_var, "Figure height")))
        if not (2 <= figw <= 40 and 2 <= figh <= 40):
            raise OptionError("Figure size: width and height must be between 2 and 40 inches.")
        def level_value(var, name):
            if custom:
                return parse_float(var.get(), name)
            try:
                return parse_float(var.get(), name, blank_ok=True)
            except OptionError:
                return None                                 # unused while "Number of levels" is chosen

        cols, pos = self._chosen_columns()
        labels = {k: (self.label_vars[k].get() if self._edited[k] else None) for k in LABEL_KEYS}
        return UserOptions(
            sheets=[s for s in self.session.sheets if self.sheet_vars.get(s) and self.sheet_vars[s].get()],
            output_dir=self.out_dir_var.get().strip(),
            header=self.header_var.get(), skip_top=top, skip_bottom=bottom, layout=self.layout_var.get(),
            columns=cols, column_positions=pos,
            interpolation=_key_of(INTERP_LABELS, self.interp_var.get(), "cubic"),
            grid_resolution=parse_int(self.res_var.get(), "Grid resolution", 10, 2000),
            fill_mode=self.fill_var.get(), custom_levels=custom,
            levels=parse_int(self.levels_var.get(), "Number of levels", 2, 100) if not custom else 15,
            level_min=level_value(self.lmin_var, "Custom levels: min"),
            level_max=level_value(self.lmax_var, "Custom levels: max"),
            level_step=level_value(self.lstep_var, "Custom levels: step"),
            cmap=self.cmap_var.get(), reverse_cmap=self.rev_var.get(),
            xlim=self._limits("xmin", "xmax", "X"), ylim=self._limits("ymin", "ymax", "Y"),
            font_size=fs, fig_w=figw, fig_h=figh,
            file_type=self.type_var.get().lower(), dpi=int(self.dpi_var.get()),
            transparent=self.trans_var.get(), include_file_name=self.incl_var.get(),
            prefix=self.prefix_var.get(), suffix=self.suffix_var.get(),
            custom_name=self.custom_var.get() if self._single_sheet() else "",
            on_exists=_key_of(EXISTS_LABELS, self.exists_var.get(), "ask"),
            **{k: v.get() for k, v in self.flags.items()}, **labels)

    def _apply_saved(self, raw: dict):
        s = clean_saved(raw)
        p, o = DEFAULT_PLOT, DEFAULT_OUTPUT
        folder = s.get("output_dir", "")
        self.out_dir_var.set(folder if folder and os.path.isdir(folder) else
                             (os.path.dirname(self.session.path) if self.session.is_open else ""))
        self.header_var.set(s.get("header", True))
        self.layout_var.set(s.get("layout", "columns"))
        self.type_var.set(s.get("file_type", o.file_type).upper())
        self.dpi_var.set(str(s.get("dpi", o.dpi)))
        self.trans_var.set(s.get("transparent", o.transparent))
        self.incl_var.set(s.get("include_file_name", False))
        self.prefix_var.set(s.get("prefix", ""))
        self.suffix_var.set(s.get("suffix", ""))
        self.exists_var.set(EXISTS_LABELS[s.get("on_exists", "ask")])
        self.interp_var.set(INTERP_LABELS[s.get("interpolation", p.interpolation)])
        self.res_var.set(str(s.get("grid_resolution", p.grid_resolution)))
        self.fill_var.set(s.get("fill_mode", p.fill_mode))
        self.levmode_var.set("custom" if s.get("custom_levels") else "number")
        self.levels_var.set(str(s.get("levels", p.levels)))
        for var, key in ((self.lmin_var, "level_min"), (self.lmax_var, "level_max"), (self.lstep_var, "level_step")):
            var.set(f"{s[key]:g}" if key in s else "")
        self.cmap_var.set(s.get("cmap", p.cmap))
        self.rev_var.set(s.get("reverse_cmap", p.reverse_cmap))
        for key, var in self.flags.items():
            var.set(s.get(key, getattr(p, "mask_outside_hull" if key == "mask_hull" else key)))
        self.font_var.set(f"{s['font_size']:g}" if "font_size" in s else "10")
        self.figw_var.set(f"{s.get('fig_w', p.figsize[0]):g}")
        self.figh_var.set(f"{s.get('fig_h', p.figsize[1]):g}")
        self._draw_cmap()

    def _save_settings(self):
        try:
            self.store.set_values(to_saved(self._collect_options()))
        except (OptionError, ValueError):
            pass                                            # keep the previously saved values
        self.store.save()

    # ================================================================== run
    def generate(self):
        if not self.session.is_open:
            messagebox.showinfo("Info", "No file selected.")
            return
        try:
            self._read_reading()
            opts = self._collect_options()
        except OptionError as e:
            messagebox.showwarning("Check your settings", str(e))
            return
        problem = validate(self.session, opts)
        if problem:
            messagebox.showwarning("Cannot generate", problem)
            return
        cfg = make_run_config(self.session, opts)
        self._save_settings()
        self.last_output_dir = cfg.output_dir
        self.progress["maximum"] = len(cfg.sheets)
        self.progress["value"] = 0
        self.status_var.set("Starting map generation…")
        self._log(f"--- Generating {len(cfg.sheets)} sheet(s) → {cfg.output_dir} ---", "info")
        self.worker = BatchWorker(cfg)
        self.worker.start()
        self._sync_states()
        self.after(100, self._poll)

    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status_var.set("Cancelling after the current sheet…")
            self.cancel_btn.set_enabled(False)

    def _poll(self):
        worker = self.worker
        if worker is None:
            return
        for ev in worker.poll():
            kind = ev[0]
            if kind == "progress":
                _, i, n, sheet = ev
                self.progress["value"] = i - 1
                self.status_var.set(f"Sheet {i} of {n}: {sheet}…")
            elif kind == "ask_overwrite":
                ans = messagebox.askyesnocancel(
                    "File already exists",
                    f"{ev[1]}\n\nYes = overwrite it\nNo = save under a new number\nCancel = skip this sheet",
                    icon="question")
                worker.answer("skip" if ans is None else "overwrite" if ans else "number")
            elif kind == "result":
                self._show_result(ev[1])
                self.progress["value"] = self.progress["value"] + 1
            elif kind == "done":
                self._finish(ev[1], ev[2])
                return
            elif kind == "crash":
                self.worker = None
                self._log(f"Unexpected error: {ev[1]}", "err")
                self.status_var.set("Stopped: unexpected error")
                self._sync_states()
                messagebox.showerror("Unexpected error", ev[1])
                return
        self.after(100, self._poll)

    def _show_result(self, r: SheetResult):
        if r.status == "saved":
            extra = f"  [{r.info}]" if r.info else ""
            self._log(f"✔ {r.sheet}: saved {r.path}{extra}", "ok")
        elif r.status == "skipped":
            self._log(f"⚠ {r.sheet}: skipped ({r.message})", "skip")
        else:
            first_line = r.message.splitlines()[0] if r.message else "unknown error"
            self._log(f"✖ {r.sheet}: failed — {first_line}", "err")

    def _finish(self, results: List[SheetResult], cancelled: bool):
        saved = [r for r in results if r.status == "saved"]
        self.worker = None
        self._sync_states()
        if cancelled:
            self.status_var.set(f"Cancelled ({len(saved)} map(s) saved)")
            self._log("Cancelled by user.", "skip")
        elif saved:
            self.status_var.set("All maps generated." if len(saved) == len(results)
                                else f"Done: {len(saved)} of {len(results)} sheet(s) saved")
        else:
            self.status_var.set("No contour maps were generated.")
        if saved:
            shown = [r.path for r in saved[:12]] + (["…"] if len(saved) > 12 else [])
            messagebox.showinfo("Done", f"{len(saved)} contour map(s) saved:\n\n" + "\n".join(shown))
        elif not cancelled:
            messagebox.showinfo("Info", "No contour maps were generated.\nSee the Results box for the reason.")

    def _open_output_folder(self):
        if self.last_output_dir and hasattr(os, "startfile"):
            os.startfile(self.last_output_dir)

    def _log(self, text: str, tag: str = "info"):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    # ================================================================== help menu
    def _build_help_menu(self):
        m = tk.Menu(self, tearoff=0, bg=C.card, fg=C.text, activebackground=C.indigo,
                    activeforeground="#ffffff", relief="flat", bd=1, font=font(10))
        m.add_command(label=f"How to use {branding.APP_NAME}", command=self._show_how_to)
        m.add_separator()
        m.add_command(label="Send a suggestion", command=lambda: dialogs.open_url(branding.SUGGESTION_URL))
        m.add_command(label="Report a problem", command=lambda: dialogs.open_url(branding.PROBLEM_URL))
        m.add_command(label="Check for updates", command=self.check_for_updates)
        m.add_separator()
        m.add_command(label="Open settings folder", command=self._open_settings_folder)
        m.add_command(label="Third-party licences", command=self._show_licences)
        m.add_command(label="Terms of use", command=self._show_terms)
        m.add_separator()
        m.add_command(label=f"About {branding.APP_NAME}", command=self._show_about)
        self.help_menu = m

    def _open_help_menu(self):
        b = self.help_btn
        x, y = b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 4
        try:
            self.help_menu.tk_popup(x, y)
        finally:
            self.help_menu.grab_release()

    def _show_how_to(self):
        dialogs.TextViewer(self, f"How to use {branding.APP_NAME}", docs.how_to_use())

    def _show_terms(self):
        dialogs.TextViewer(self, "Terms of use", docs.terms())

    def _show_licences(self):
        dialogs.TextViewer(self, "Third-party licences", docs.third_party(), width=860, height=640)

    def _show_about(self):
        dialogs.AboutDialog(self, self.check_for_updates, self._show_licences, self._show_terms)

    def _open_settings_folder(self):
        self._save_settings()                              # makes sure the file exists
        if self.store.path_used:
            dialogs.open_folder(os.path.dirname(self.store.path_used))
        else:
            messagebox.showinfo("Settings folder", "Settings could not be saved on this PC.")

    def check_for_updates(self):
        """Ask GitHub for the latest release on a background thread (only when the user asks)."""
        import queue
        import threading
        if self._update_q is not None:
            return
        self._update_q = queue.Queue()
        self.status_var.set("Checking for updates…")

        def work(q=self._update_q):
            try:
                q.put(("ok", updates.check()))
            except updates.UpdateError as e:
                q.put(("err", str(e)))
            except Exception as e:
                q.put(("err", f"Unexpected problem: {e}"))
        threading.Thread(target=work, daemon=True).start()
        self.after(150, self._poll_update)

    def _poll_update(self):
        q = self._update_q
        if q is None:
            return
        try:
            kind, payload = q.get_nowait()
        except Exception:
            self.after(150, self._poll_update)
            return
        self._update_q = None
        self.status_var.set("Ready.")
        if kind == "err":
            if messagebox.askyesno("Check for updates", f"{payload}\n\nOpen the download page instead?"):
                dialogs.open_url(branding.RELEASES_URL)
            return
        r = payload
        if r.status == "newer":
            if messagebox.askyesno("Update available",
                                   f"Version {r.latest} is available. You have {r.current}.\n\n"
                                   "Open the download page?"):
                dialogs.open_url(r.url)
        elif r.status == "ahead":
            messagebox.showinfo("Check for updates", f"You have version {r.current}, which is newer than "
                                                     f"the latest public release ({r.latest}).")
        else:
            messagebox.showinfo("Check for updates", f"You have the latest version ({r.current}).")

    def _on_close(self):
        try:
            self._save_settings()
        finally:
            if self._preview_job is not None:
                self.after_cancel(self._preview_job)
            if self.worker:
                self.worker.cancel()
            self.destroy()


def main():
    if os.name == "nt":                                    # crisp text on high-DPI screens
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()
