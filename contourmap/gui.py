"""tkinter front end. Presentation only: all real work lives in the other modules."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import List, Optional

from . import presets
from .data_loader import DataLoadError, SUPPORTED_EXTS, list_sheets
from .presets import ModePreset
from .runner import RunConfig, SheetResult
from .worker import BatchWorker

APP_TITLE = "Contour Map Generator"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x600")
        self.minsize(640, 480)

        self.preset: ModePreset = presets.MODES[presets.DEFAULT_MODE]
        self.file_path: Optional[str] = None
        self.sheets: List[str] = []
        self.worker: Optional[BatchWorker] = None

        self._build_mode_bar()
        self._build_file_frame()
        self._build_run_frame()
        self._build_log()
        self._on_mode_change()

    # ------------------------------------------------------------------ layout
    def _build_mode_bar(self):
        bar = ttk.Frame(self, padding=(10, 10, 10, 0))
        bar.pack(fill="x")
        ttk.Label(bar, text="Mode", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.mode_var = tk.StringVar(value=self.preset.name)
        self.mode_box = ttk.Combobox(bar, textvariable=self.mode_var, state="readonly", width=28,
                                     values=list(presets.MODES))
        self.mode_box.pack(side="left", padx=8)
        self.mode_box.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())
        self.mode_desc = ttk.Label(self, wraplength=720, justify="left", padding=(10, 4))
        self.mode_desc.pack(fill="x")

    def _build_file_frame(self):
        self.file_frame = ttk.LabelFrame(self, text="Data file", padding=8)
        self.file_frame.pack(fill="x", padx=10, pady=4)
        row = ttk.Frame(self.file_frame)
        row.pack(fill="x")
        self.open_btn = ttk.Button(row, text="Open file…", command=self.open_file)
        self.open_btn.pack(side="left")
        self.path_var = tk.StringVar(value="No file selected")
        ttk.Label(row, textvariable=self.path_var, anchor="w").pack(side="left", padx=10, fill="x", expand=True)
        self.sheets_var = tk.StringVar(value="")
        ttk.Label(self.file_frame, textvariable=self.sheets_var, foreground="#555").pack(anchor="w", pady=(4, 0))
        self.where_var = tk.StringVar(value="")
        ttk.Label(self.file_frame, textvariable=self.where_var, foreground="#555").pack(anchor="w")

    def _build_run_frame(self):
        frame = ttk.Frame(self, padding=(10, 4))
        frame.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.gen_btn = ttk.Button(row, text="Generate maps", command=self.generate)
        self.gen_btn.pack(side="left")
        self.cancel_btn = ttk.Button(row, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="Status: waiting for input…")
        ttk.Label(row, textvariable=self.status_var).pack(side="left", padx=10)
        self.progress = ttk.Progressbar(frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(6, 0))

    def _build_log(self):
        box = ttk.LabelFrame(self, text="Results", padding=6)
        box.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.log = ScrolledText(box, height=10, state="disabled", wrap="word", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok", foreground="#1b7f3b")
        self.log.tag_config("skip", foreground="#9a6700")
        self.log.tag_config("err", foreground="#b3261e")
        self.log.tag_config("info", foreground="#333333")

    # ------------------------------------------------------------------ mode handling
    def _on_mode_change(self):
        self.preset = presets.MODES[self.mode_var.get()]
        note = self.preset.description
        if not self.preset.available:
            note += "\n(This mode is not available yet in this build.)"
        self.mode_desc.config(text=note)
        if self.preset.default_output == "input_folder":
            self.where_var.set("Images are saved next to the data file, named <file>_<sheet>.png")
        else:
            self.where_var.set("")
        self._refresh_buttons()

    def _refresh_buttons(self):
        busy = self.worker is not None and self.worker.running
        can_run = (self.file_path is not None and bool(self.sheets) and self.preset.available and not busy)
        self.gen_btn.config(state="normal" if can_run else "disabled")
        self.cancel_btn.config(state="normal" if busy else "disabled")
        self.open_btn.config(state="disabled" if busy else "normal")
        self.mode_box.config(state="disabled" if busy else "readonly")

    # ------------------------------------------------------------------ file
    def open_file(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTS)
        path = filedialog.askopenfilename(
            title="Select a data file",
            filetypes=[("Data files", exts), ("All files", "*.*")])
        if not path:
            return
        try:
            sheets = list_sheets(path)
        except DataLoadError as e:
            messagebox.showerror("Cannot open file", str(e))
            return
        if not sheets:
            messagebox.showerror("Empty file", "This file contains no sheets.")
            return
        self.file_path, self.sheets = path, sheets
        self.path_var.set(path)
        shown = ", ".join(sheets[:8]) + (" …" if len(sheets) > 8 else "")
        self.sheets_var.set(f"{len(sheets)} sheet(s): {shown}")
        self._log(f"Loaded {os.path.basename(path)} — {len(sheets)} sheet(s)", "info")
        self._refresh_buttons()

    # ------------------------------------------------------------------ run
    def generate(self):
        if not self.file_path:
            messagebox.showinfo("Info", "No file selected.")
            return
        cfg = RunConfig(path=self.file_path, preset=self.preset, sheets=list(self.sheets),
                        output_dir=os.path.dirname(self.file_path))
        self.progress["maximum"] = len(cfg.sheets)
        self.progress["value"] = 0
        self.status_var.set("Starting map generation…")
        self._log(f"--- Generating {len(cfg.sheets)} sheet(s) [{self.preset.name}] ---", "info")
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
            elif kind == "result":
                self._show_result(ev[1])
                self.progress["value"] = self.progress["value"] + 1
            elif kind == "done":
                self._finish(ev[1], ev[2])
                return
            elif kind == "crash":
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
            messagebox.showinfo("Done", "Contour maps saved:\n\n" + "\n".join(r.path for r in saved))
        elif not cancelled:
            messagebox.showinfo("Info", "No contour maps were generated.\nSee the Results box for the reason.")

    def _log(self, text: str, tag: str = "info"):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")


def main():
    App().mainloop()
