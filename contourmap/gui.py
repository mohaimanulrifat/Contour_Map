"""tkinter front end. Presentation only: all real work lives in the other modules.

Half Cell Potential is a locked *format*: the window shows just the file, a read-only preview
and Generate. Universal shows the settings tabs (Data / Labels / Output).
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from . import presets
from .data_loader import DataLoadError, SUPPORTED_EXTS
from .engine import FILE_TYPES
from .presets import ModePreset
from .runner import SheetResult
from .session import (DPI_CHOICES, DataSession, UserOptions, clean_saved, make_run_config,
                      to_saved, validate)
from .settings import SettingsStore
from .worker import BatchWorker

APP_TITLE = "Contour Map Generator"
EXISTS_LABELS = {"ask": "Ask me", "number": "Add a number: name (1)", "overwrite": "Overwrite"}
LABEL_KEYS = ("title", "xlabel", "ylabel", "cbar_label")


class App(tk.Tk):
    def __init__(self, settings: Optional[SettingsStore] = None):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x760")
        self.minsize(900, 600)

        self.store = settings or SettingsStore()
        self.session = DataSession()
        self.worker: Optional[BatchWorker] = None
        self.last_output_dir: Optional[str] = None
        self.sheet_vars: Dict[str, tk.BooleanVar] = {}
        self.sheet_checks: List[ttk.Checkbutton] = []
        self._edited = {k: False for k in LABEL_KEYS}      # label box changed by the user?
        self._filling = False                              # programmatic label fill in progress

        start = self.store.get("last_mode")
        self.preset: ModePreset = presets.MODES.get(start) or presets.MODES[presets.DEFAULT_MODE]
        if not self.preset.available:
            self.preset = presets.MODES[presets.DEFAULT_MODE]
        self._shown_mode = self.preset.name

        self._make_vars()
        self._build_mode_bar()
        self._build_file_row()
        self._build_body()
        self._build_run_row()
        self._apply_saved(self.store.mode(self.preset.name))
        self._apply_mode_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================== variables
    def _make_vars(self):
        d = presets.UNIVERSAL.output
        self.mode_var = tk.StringVar(value=self.preset.name)
        self.path_var = tk.StringVar(value="No file selected")
        self.header_var = tk.BooleanVar(value=True)
        self.all_var = tk.BooleanVar(value=True)
        self.preview_var = tk.StringVar()
        self.preview_info = tk.StringVar()
        self.label_vars = {k: tk.StringVar() for k in LABEL_KEYS}
        for k, v in self.label_vars.items():
            v.trace_add("write", lambda *a, key=k: self._label_typed(key))
        self.out_dir_var = tk.StringVar()
        self.type_var = tk.StringVar(value=d.file_type.upper())
        self.dpi_var = tk.StringVar(value=str(d.dpi))
        self.trans_var = tk.BooleanVar(value=d.transparent)
        self.incl_var = tk.BooleanVar(value=False)
        self.prefix_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        self.custom_var = tk.StringVar()
        self.exists_var = tk.StringVar(value=EXISTS_LABELS[presets.UNIVERSAL.naming.on_exists])
        self.status_var = tk.StringVar(value="Status: waiting for input…")

    # ================================================================== layout
    def _build_mode_bar(self):
        bar = ttk.Frame(self, padding=(10, 10, 10, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="Mode", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.mode_box = ttk.Combobox(bar, textvariable=self.mode_var, state="readonly", width=28,
                                     values=[m.name for m in presets.MODES.values() if m.available])
        self.mode_box.pack(side="left", padx=8)
        self.mode_box.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())
        self.mode_desc = ttk.Label(self, wraplength=1050, justify="left", padding=(10, 4))
        self.mode_desc.pack(fill="x")

    def _build_file_row(self):
        row = ttk.Frame(self, padding=(10, 0, 10, 4))
        row.pack(fill="x")
        self.open_btn = ttk.Button(row, text="Open file…", command=self.open_file)
        self.open_btn.pack(side="left")
        ttk.Label(row, textvariable=self.path_var, anchor="w").pack(side="left", padx=10, fill="x", expand=True)

    def _build_body(self):
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=4)
        self.left = ttk.Frame(pane, width=430)
        right = ttk.Frame(pane)
        pane.add(self.left, weight=0)
        pane.add(right, weight=1)

        # Locked format summary (Half Cell Potential)
        self.fixed_panel = ttk.LabelFrame(self.left, text="Automatic settings", padding=10)
        self.fixed_text = ttk.Label(self.fixed_panel, wraplength=390, justify="left")
        self.fixed_text.pack(anchor="w")

        # Settings tabs (Universal)
        self.tabs = ttk.Notebook(self.left)
        self._build_data_tab()
        self._build_labels_tab()
        self._build_output_tab()

        self._build_preview(right)
        self._build_log(right)

    def _build_data_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="Data")
        ttk.Checkbutton(tab, text="Use first row as column titles", variable=self.header_var,
                        command=self._on_header_toggle).pack(anchor="w")
        ttk.Separator(tab).pack(fill="x", pady=8)
        ttk.Label(tab, text="Sheets to process", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.all_check = ttk.Checkbutton(tab, text="Process all sheets", variable=self.all_var,
                                         command=self._on_all_toggle)
        self.all_check.pack(anchor="w", pady=(2, 4))
        box = ttk.Frame(tab, relief="sunken", borderwidth=1)
        box.pack(fill="both", expand=True)
        self.sheet_canvas = tk.Canvas(box, height=170, highlightthickness=0, background="white")
        sb = ttk.Scrollbar(box, orient="vertical", command=self.sheet_canvas.yview)
        self.sheet_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.sheet_canvas.pack(side="left", fill="both", expand=True)
        self.sheet_inner = tk.Frame(self.sheet_canvas, background="white")
        self.sheet_canvas.create_window((0, 0), window=self.sheet_inner, anchor="nw")
        self.sheet_inner.bind("<Configure>", lambda e: self.sheet_canvas.configure(
            scrollregion=self.sheet_canvas.bbox("all")))
        for ev, delta in (("<MouseWheel>", None), ("<Button-4>", -1), ("<Button-5>", 1)):
            self.sheet_canvas.bind(ev, lambda e, d=delta: self._wheel(e, d))
            self.sheet_inner.bind(ev, lambda e, d=delta: self._wheel(e, d))

    def _wheel(self, event, delta):
        step = delta if delta is not None else (-1 if event.delta > 0 else 1)
        self.sheet_canvas.yview_scroll(step, "units")

    def _build_labels_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="Labels")
        ttk.Label(tab, text="Pre-filled from the column titles; edit to override.\n"
                            "Untouched boxes follow each sheet's own titles.",
                  foreground="#555", justify="left").pack(anchor="w", pady=(0, 8))
        for key, text in (("title", "Plot title"), ("xlabel", "X axis name"),
                          ("ylabel", "Y axis name"), ("cbar_label", "Colorbar label")):
            ttk.Label(tab, text=text).pack(anchor="w")
            ttk.Entry(tab, textvariable=self.label_vars[key]).pack(fill="x", pady=(0, 6))
        ttk.Button(tab, text="Reset to column titles", command=self._reset_labels).pack(anchor="w", pady=4)

    def _build_output_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="Output")
        tab.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(tab, text="Output folder").grid(row=r, column=0, sticky="w")
        r += 1
        f = ttk.Frame(tab)
        f.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Entry(f, textvariable=self.out_dir_var).pack(side="left", fill="x", expand=True)
        ttk.Button(f, text="Browse…", command=self._browse_out).pack(side="left", padx=(6, 0))
        r += 1
        ttk.Label(tab, text="File type").grid(row=r, column=0, sticky="w")
        ttk.Label(tab, text="DPI").grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        self.type_box = ttk.Combobox(tab, textvariable=self.type_var, state="readonly", width=8,
                                     values=[t.upper() for t in FILE_TYPES])
        self.type_box.grid(row=r, column=0, sticky="w")
        self.type_box.bind("<<ComboboxSelected>>", lambda e: self._sync_type())
        ttk.Combobox(tab, textvariable=self.dpi_var, state="readonly", width=6,
                     values=[str(d) for d in DPI_CHOICES]).grid(row=r, column=1, sticky="w", padx=8)
        r += 1
        self.trans_check = ttk.Checkbutton(tab, text="Transparent background", variable=self.trans_var)
        self.trans_check.grid(row=r, column=0, columnspan=3, sticky="w", pady=(4, 0))
        r += 1
        ttk.Separator(tab).grid(row=r, column=0, columnspan=3, sticky="ew", pady=8)
        r += 1
        ttk.Label(tab, text="File names", font=("Segoe UI", 9, "bold")).grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1
        ttk.Label(tab, text="Default is the sheet name.", foreground="#555").grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1
        ttk.Checkbutton(tab, text="Include the data file name",
                        variable=self.incl_var).grid(row=r, column=0, columnspan=3, sticky="w")
        for text, var in (("Prefix", self.prefix_var), ("Suffix", self.suffix_var)):
            r += 1
            ttk.Label(tab, text=text).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(tab, textvariable=var).grid(row=r, column=1, columnspan=2, sticky="ew", padx=8)
        r += 1
        ttk.Label(tab, text="Custom name").grid(row=r, column=0, sticky="w", pady=2)
        self.custom_entry = ttk.Entry(tab, textvariable=self.custom_var)
        self.custom_entry.grid(row=r, column=1, columnspan=2, sticky="ew", padx=8)
        r += 1
        self.custom_hint = ttk.Label(tab, text="", foreground="#555")
        self.custom_hint.grid(row=r, column=1, columnspan=2, sticky="w", padx=8)
        r += 1
        ttk.Label(tab, text="If the file exists").grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(tab, textvariable=self.exists_var, state="readonly", width=22,
                     values=list(EXISTS_LABELS.values())).grid(row=r, column=1, columnspan=2, sticky="w", padx=8, pady=(6, 0))

    def _build_preview(self, parent):
        box = ttk.LabelFrame(parent, text="Data preview", padding=6)
        box.pack(fill="both", expand=True)
        top = ttk.Frame(box)
        top.pack(fill="x", pady=(0, 4))
        ttk.Label(top, text="Sheet").pack(side="left")
        self.preview_box = ttk.Combobox(top, textvariable=self.preview_var, state="readonly", width=30)
        self.preview_box.pack(side="left", padx=6)
        self.preview_box.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())
        ttk.Label(top, textvariable=self.preview_info, foreground="#555").pack(side="left", padx=8)
        grid = ttk.Frame(box)
        grid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(grid, show="headings", height=9)
        vs = ttk.Scrollbar(grid, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        grid.rowconfigure(0, weight=1)
        grid.columnconfigure(0, weight=1)

    def _build_log(self, parent):
        box = ttk.LabelFrame(parent, text="Results", padding=6)
        box.pack(fill="both", expand=True, pady=(6, 0))
        self.log = ScrolledText(box, height=9, state="disabled", wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok", foreground="#1b7f3b")
        self.log.tag_config("skip", foreground="#9a6700")
        self.log.tag_config("err", foreground="#b3261e")
        self.log.tag_config("info", foreground="#333333")

    def _build_run_row(self):
        frame = ttk.Frame(self, padding=(10, 4, 10, 10))
        frame.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.gen_btn = ttk.Button(row, text="Generate maps", command=self.generate)
        self.gen_btn.pack(side="left")
        self.cancel_btn = ttk.Button(row, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.folder_btn = ttk.Button(row, text="Open output folder", command=self._open_output_folder,
                                     state="disabled")
        if hasattr(os, "startfile"):                     # Windows only
            self.folder_btn.pack(side="left")
        ttk.Label(row, textvariable=self.status_var).pack(side="left", padx=12)
        self.progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(6, 0))

    # ================================================================== mode handling
    def _on_mode_change(self):
        self._save_settings()                            # remember the mode we are leaving
        self.preset = presets.MODES[self.mode_var.get()]
        self._shown_mode = self.preset.name
        self._apply_saved(self.store.mode(self.preset.name))
        self._apply_mode_ui()
        if self.session.is_open:
            self._after_data_change(reset_labels=True)

    def _apply_mode_ui(self):
        p = self.preset
        self.mode_desc.config(text=p.description)
        self.mode_var.set(p.name)
        if p.customizable:
            self.fixed_panel.pack_forget()
            self.tabs.pack(fill="both", expand=True)
        else:
            self.tabs.pack_forget()
            self.fixed_panel.pack(fill="x")
            self._refresh_fixed_text()
        self._refresh_buttons()

    def _refresh_fixed_text(self):
        p = self.preset
        n = len(self.session.sheets)
        sheets = f"all {n} sheet(s) of the file" if self.session.is_open else "every sheet of the file"
        pattern = p.naming.pattern.replace("{file}", "<file>").replace("{sheet}", "<sheet>")
        self.fixed_text.config(text=(
            "Nothing to set up: open a file and press Generate.\n\n"
            f"•  Maps are made for {sheets}.\n"
            "•  Row 1 = column titles; X, Y, Z are found by header name, else the first three columns.\n"
            f"•  Output: {p.output.file_type.upper()}, {p.output.dpi} DPI, saved next to the data file "
            f"as {pattern}.{p.output.file_type}\n"
            "•  Plot style is fixed."))

    def _refresh_buttons(self):
        busy = self.worker is not None and self.worker.running
        can_run = self.session.is_open and not busy
        self.gen_btn.config(state="normal" if can_run else "disabled")
        self.cancel_btn.config(state="normal" if busy else "disabled")
        self.open_btn.config(state="disabled" if busy else "normal")
        self.mode_box.config(state="disabled" if busy else "readonly")
        self.folder_btn.config(state="normal" if (self.last_output_dir and not busy) else "disabled")

    # ================================================================== file + preview
    def open_file(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTS)
        start = self.store.get("last_open_dir")
        path = filedialog.askopenfilename(
            title="Select a data file", initialdir=start if start and os.path.isdir(start) else None,
            filetypes=[("Data files", exts), ("All files", "*.*")])
        if not path:
            return
        header = self.header_var.get() if self.preset.customizable else self.preset.header_row
        try:
            self.session.open(path, header=header)
        except DataLoadError as e:
            messagebox.showerror("Cannot open file", str(e))
            return
        self.store.set("last_open_dir", os.path.dirname(path))
        self.path_var.set(path)
        if not self.out_dir_var.get() or not os.path.isdir(self.out_dir_var.get()):
            self.out_dir_var.set(os.path.dirname(path))
        self._log(f"Loaded {os.path.basename(path)}: {len(self.session.sheets)} sheet(s)", "info")
        self._build_sheet_list()
        self.preview_box.config(values=self.session.sheets)
        self.preview_var.set(self.session.sheets[0])
        self._after_data_change(reset_labels=True)
        self._refresh_fixed_text()
        self._refresh_buttons()

    def _after_data_change(self, reset_labels: bool = False):
        if reset_labels:
            self._edited = {k: False for k in LABEL_KEYS}
        self._refresh_preview()

    def _on_header_toggle(self):
        if not self.session.is_open:
            return
        self.session.set_header(self.header_var.get())
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
        for cid, title, i in zip(ids, cols, range(len(cols))):
            longest = max([len(title)] + [len(r[i]) for r in rows])
            self.tree.heading(cid, text=title)
            self.tree.column(cid, width=max(60, min(240, longest * 8 + 16)), stretch=False, anchor="w")
        for r in rows:
            self.tree.insert("", "end", values=r)
        self.preview_info.set(f"first {len(rows)} of {total} rows · {len(cols)} columns")
        self._prefill_labels()

    # ================================================================== sheet checklist
    def _build_sheet_list(self):
        for w in self.sheet_inner.winfo_children():
            w.destroy()
        self.sheet_vars, self.sheet_checks = {}, []
        for name in self.session.sheets:
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(self.sheet_inner, text=name, variable=var, command=self._on_sheet_toggle)
            cb.pack(anchor="w", padx=4)
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

    def _single_sheet(self) -> bool:
        return sum(v.get() for v in self.sheet_vars.values()) == 1

    def _sync_sheet_state(self):
        for cb in self.sheet_checks:
            cb.state(["disabled"] if self.all_var.get() else ["!disabled"])
        one = self._single_sheet()
        self.custom_entry.config(state="normal" if one else "disabled")
        self.custom_hint.config(text="" if one else "(single sheet only)")

    # ================================================================== labels
    def _label_typed(self, key):
        if not self._filling:
            self._edited[key] = True

    def _prefill_labels(self):
        if not self.session.is_open or not self.preset.customizable:
            return
        sheet = self.preview_var.get()
        try:
            texts = self.session.default_labels(sheet, self.preset)
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

    # ================================================================== output options
    def _browse_out(self):
        start = self.out_dir_var.get()
        d = filedialog.askdirectory(title="Output folder", initialdir=start if os.path.isdir(start) else None)
        if d:
            self.out_dir_var.set(os.path.normpath(d))

    def _sync_type(self):
        jpg = self.type_var.get() == "JPG"
        if jpg:
            self.trans_var.set(False)
        self.trans_check.state(["disabled"] if jpg else ["!disabled"])

    # ================================================================== options <-> widgets
    def _collect_options(self) -> UserOptions:
        exists = next((k for k, v in EXISTS_LABELS.items() if v == self.exists_var.get()), "ask")
        labels = {k: (self.label_vars[k].get() if self._edited[k] else None) for k in LABEL_KEYS}
        return UserOptions(
            sheets=[s for s in self.session.sheets if self.sheet_vars.get(s) and self.sheet_vars[s].get()],
            output_dir=self.out_dir_var.get().strip(), header=self.header_var.get(),
            file_type=self.type_var.get().lower(), dpi=int(self.dpi_var.get()),
            transparent=self.trans_var.get(), include_file_name=self.incl_var.get(),
            prefix=self.prefix_var.get(), suffix=self.suffix_var.get(),
            custom_name=self.custom_var.get() if self._single_sheet() else "",
            on_exists=exists, **labels)

    def _apply_saved(self, raw: dict):
        s = clean_saved(raw)
        d = self.preset.output
        self.header_var.set(s.get("header", self.preset.header_row))
        folder = s.get("output_dir", "")
        self.out_dir_var.set(folder if folder and os.path.isdir(folder) else
                             (os.path.dirname(self.session.path) if self.session.is_open else ""))
        self.type_var.set(s.get("file_type", d.file_type).upper())
        self.dpi_var.set(str(s.get("dpi", d.dpi)))
        self.trans_var.set(s.get("transparent", d.transparent))
        self.incl_var.set(s.get("include_file_name", self.preset.naming.pattern.startswith("{file}")))
        self.prefix_var.set(s.get("prefix", ""))
        self.suffix_var.set(s.get("suffix", ""))
        self.exists_var.set(EXISTS_LABELS[s.get("on_exists", self.preset.naming.on_exists)])
        self.custom_var.set("")
        self._sync_type()
        if self.session.is_open:
            self.session.set_header(self.header_var.get() if self.preset.customizable
                                    else self.preset.header_row)

    def _save_settings(self):
        self.store.set("last_mode", self._shown_mode)
        prev = presets.MODES.get(self._shown_mode)
        if prev and prev.customizable:
            self.store.set_mode(prev.name, to_saved(self._collect_options()))
        self.store.save()

    # ================================================================== run
    def generate(self):
        if not self.session.is_open:
            messagebox.showinfo("Info", "No file selected.")
            return
        opts = self._collect_options()
        problem = validate(self.preset, self.session, opts)
        if problem:
            messagebox.showwarning("Cannot generate", problem)
            return
        cfg = make_run_config(self.preset, self.session, opts)
        self._save_settings()
        self.last_output_dir = cfg.output_dir
        self.progress["maximum"] = len(cfg.sheets)
        self.progress["value"] = 0
        self.status_var.set("Starting map generation…")
        self._log(f"--- Generating {len(cfg.sheets)} sheet(s) [{self.preset.name}] → {cfg.output_dir} ---", "info")
        self.worker = BatchWorker(cfg)
        self.worker.start()
        self._refresh_buttons()
        self.after(100, self._poll)

    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status_var.set("Cancelling after the current sheet…")
            self.cancel_btn.config(state="disabled")

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
                self._refresh_buttons()
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
        self._refresh_buttons()
        if cancelled:
            self.status_var.set(f"Cancelled ({len(saved)} map(s) saved)")
            self._log("Cancelled by user.", "skip")
        elif saved:
            self.status_var.set("✅ All maps generated successfully!" if len(saved) == len(results)
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

    def _on_close(self):
        try:
            self._save_settings()
        finally:
            if self.worker:
                self.worker.cancel()
            self.destroy()


def main():
    App().mainloop()
