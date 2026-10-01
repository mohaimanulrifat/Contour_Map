"""Application logic between the GUI and the engine. No tkinter in here.

DataSession   the opened file: cached sheets, preview rows, column guesses, data check
UserOptions   what the user chose in the GUI (plain, typed data; saved/restored as settings)
validate / make_run_config    explain what is wrong, or build the RunConfig
"""
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from typing import Dict, List, Optional, Tuple

import matplotlib
import pandas as pd

from .data_loader import (GRID_COLUMNS, DataLoadError, LoadOptions, SheetSkipped, extract_xyz,
                          guess_xyz, list_sheets, load_sheet)
from .defaults import (COLORMAPS, FILL_CHOICES, INTERPOLATION_CHOICES, OutputSettings,
                       PlotSettings)
from .engine import FILE_TYPES
from .naming import ON_EXISTS_CHOICES, NamingOptions
from .runner import LAYOUTS, RunConfig, load_options_for, prepare_frame

PREVIEW_ROWS = 20
DPI_CHOICES = (72, 150, 300, 600)


class OptionError(ValueError):
    """A setting has a value the user must fix (message is shown in a dialog)."""


# ------------------------------------------------------------------------------ parsing helpers
def parse_float(text: str, name: str, blank_ok: bool = False) -> Optional[float]:
    t = str(text).strip().replace(",", ".")
    if not t:
        if blank_ok:
            return None
        raise OptionError(f"{name}: please enter a number.")
    try:
        v = float(t)
    except ValueError:
        raise OptionError(f"{name}: '{text}' is not a number.")
    if v != v or v in (float("inf"), float("-inf")):
        raise OptionError(f"{name}: '{text}' is not a usable number.")
    return v


def parse_int(text: str, name: str, lo: int, hi: int) -> int:
    v = parse_float(text, name)
    if v != int(v):
        raise OptionError(f"{name}: please enter a whole number.")
    if not lo <= v <= hi:
        raise OptionError(f"{name}: must be between {lo} and {hi}.")
    return int(v)


# ------------------------------------------------------------------------------ data session
class DataSession:
    """The currently opened data file and how it is being read."""

    def __init__(self):
        self.path: Optional[str] = None
        self.sheets: List[str] = []
        self.load = LoadOptions()
        self.layout = "columns"
        self._cache: Dict[tuple, pd.DataFrame] = {}

    @property
    def is_open(self) -> bool:
        return self.path is not None

    @property
    def effective_load(self) -> LoadOptions:
        return load_options_for(RunConfig(path="", sheets=[], output_dir="", load=self.load,
                                          layout=self.layout))

    def open(self, path: str) -> None:
        """Open a file. Raises DataLoadError (friendly message) if unusable."""
        sheets = list_sheets(path)
        if not sheets:
            raise DataLoadError("This file contains no sheets.")
        self.path, self.sheets, self._cache = path, sheets, {}
        if len(sheets) == 1:
            df = self.frame(sheets[0])
            if df.shape[1] == 0 or df.empty:
                self.close()
                raise DataLoadError("This file is empty: it has no data rows to plot.")

    def close(self):
        self.path, self.sheets, self._cache = None, [], {}

    def set_reading(self, header: bool, skip_top: int, skip_bottom: int, layout: str) -> None:
        """Change how sheets are read; cached tables are dropped only if something changed."""
        new = replace(self.load, header=header, skip_top=skip_top, skip_bottom=skip_bottom)
        if new != self.load or layout != self.layout:
            self.load, self.layout, self._cache = new, layout, {}

    def frame(self, sheet: str) -> pd.DataFrame:
        opts = self.effective_load
        key = (sheet, opts)
        if key not in self._cache:
            self._cache[key] = load_sheet(self.path, sheet, opts)
        return self._cache[key]

    def preview(self, sheet: str, n: int = PREVIEW_ROWS) -> Tuple[List[str], List[List[str]], int]:
        """(column titles, first n rows as strings, total rows)."""
        df = self.frame(sheet)
        rows = [["" if pd.isna(v) else str(v) for v in r] for r in df.head(n).itertuples(index=False)]
        return [str(c) for c in df.columns], rows, len(df)

    def column_names(self, sheet: str) -> List[str]:
        return [str(c) for c in self.frame(sheet).columns]

    def guess_columns(self, sheet: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if self.layout == "grid":
            return (None, None, None)
        df = self.frame(sheet)
        x, y, z = guess_xyz(df)
        return tuple(None if c is None else str(c) for c in (x, y, z))

    def default_labels(self, sheet: str, columns: Optional[Tuple[str, str, str]] = None) -> Dict[str, str]:
        """Axis/colorbar texts from the column titles of `sheet` ('' if not available)."""
        if self.layout == "grid":
            x, y, z = GRID_COLUMNS
        else:
            x, y, z = columns or self.guess_columns(sheet)
        return {"xlabel": x or "", "ylabel": y or "", "cbar_label": z or "", "title": ""}

    def check(self, sheet: str, columns=None, positions=None) -> Tuple[bool, str]:
        """(ok, text) describing what the chosen columns hold: valid points and dropped rows."""
        try:
            frame, cols, _ = prepare_frame(self.frame(sheet), self.layout, columns, positions)
            data = extract_xyz(frame, *cols)
        except SheetSkipped as e:
            return False, str(e).capitalize()
        except DataLoadError as e:
            return False, str(e)
        if len(data.x) == 0:
            return False, "No numeric X/Y/Z rows found with these columns."
        return True, data.summary().capitalize()


# ------------------------------------------------------------------------------ user choices
@dataclass
class UserOptions:
    sheets: List[str]
    output_dir: str = ""
    # data
    header: bool = True
    skip_top: int = 0
    skip_bottom: int = 0
    layout: str = "columns"
    columns: Optional[Tuple[str, str, str]] = None            # None = automatic
    column_positions: Optional[Tuple[int, int, int]] = None
    # plot
    interpolation: str = "cubic"
    grid_resolution: int = 200
    fill_mode: str = "both"
    custom_levels: bool = False
    levels: int = 15
    level_min: Optional[float] = None
    level_max: Optional[float] = None
    level_step: Optional[float] = None
    cmap: str = "viridis"
    reverse_cmap: bool = False
    show_labels: bool = True
    show_points: bool = False
    show_grid: bool = True
    show_colorbar: bool = True
    equal_aspect: bool = False
    invert_x: bool = False
    invert_y: bool = False
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    font_size: Optional[float] = None
    fig_w: float = 8
    fig_h: float = 7
    mask_hull: bool = False
    # labels: None = take from the column titles of each sheet; any string (even "") = user text
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    cbar_label: Optional[str] = None
    # output
    file_type: str = "png"
    dpi: int = 300
    transparent: bool = False
    include_file_name: bool = False
    prefix: str = ""
    suffix: str = ""
    custom_name: str = ""
    on_exists: str = "ask"


def _is_bool(v): return isinstance(v, bool)
def _is_str(v): return isinstance(v, str)
def _num(lo, hi): return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi
def _one_of(*c): return lambda v: v in c


# settings kept between runs, with a validator for each (a hand-edited file can't break the GUI)
SAVED_SCHEMA = {
    "output_dir": _is_str, "header": _is_bool, "layout": _one_of(*LAYOUTS),
    "file_type": _one_of(*FILE_TYPES), "dpi": _one_of(*DPI_CHOICES), "transparent": _is_bool,
    "include_file_name": _is_bool, "prefix": _is_str, "suffix": _is_str,
    "on_exists": _one_of(*ON_EXISTS_CHOICES),
    "interpolation": _one_of(*INTERPOLATION_CHOICES), "grid_resolution": _num(10, 2000),
    "fill_mode": _one_of(*FILL_CHOICES), "custom_levels": _is_bool, "levels": _num(2, 100),
    "level_min": _num(-1e12, 1e12), "level_max": _num(-1e12, 1e12), "level_step": _num(1e-12, 1e12),
    "cmap": _one_of(*COLORMAPS), "reverse_cmap": _is_bool, "show_labels": _is_bool,
    "show_points": _is_bool, "show_grid": _is_bool, "show_colorbar": _is_bool,
    "equal_aspect": _is_bool, "invert_x": _is_bool, "invert_y": _is_bool,
    "font_size": _num(4, 40), "fig_w": _num(2, 40), "fig_h": _num(2, 40), "mask_hull": _is_bool,
}


def to_saved(opts: UserOptions) -> Dict[str, object]:
    d = asdict(opts)
    return {k: d[k] for k in SAVED_SCHEMA if d[k] is not None}


def clean_saved(raw: Dict[str, object]) -> Dict[str, object]:
    return {k: raw[k] for k, ok in SAVED_SCHEMA.items() if k in raw and ok(raw[k])}


# ------------------------------------------------------------------------------ validation
def folder_problem(folder: str) -> Optional[str]:
    """Why `folder` can't be used for output (None if it is fine; it is created if missing)."""
    if not folder.strip():
        return "Please choose an output folder."
    try:
        os.makedirs(folder, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder):
            pass
    except OSError as e:
        return f"Cannot write to the output folder:\n{folder}\n\n{e.strerror or e}"
    return None


def plot_problem(o: UserOptions) -> Optional[str]:
    if o.interpolation not in INTERPOLATION_CHOICES or o.fill_mode not in FILL_CHOICES:
        return "Unknown interpolation or style."
    if o.cmap not in matplotlib.colormaps:
        return f"Unknown colormap '{o.cmap}'."
    if o.custom_levels:
        if None in (o.level_min, o.level_max, o.level_step):
            return "Custom levels: please fill in min, max and step."
        if o.level_max <= o.level_min:
            return "Custom levels: max must be larger than min."
        if o.level_step <= 0:
            return "Custom levels: step must be above 0."
        n = (o.level_max - o.level_min) / o.level_step
        if n > 500:
            return f"Custom levels: this would draw {int(n)} levels; use a larger step."
    for name, lim in (("X", o.xlim), ("Y", o.ylim)):
        if lim is not None and lim[0] >= lim[1]:
            return f"{name} axis limits: min must be smaller than max."
    return None


def validate(session: DataSession, opts: UserOptions) -> Optional[str]:
    """A message for a messagebox if the run can't start, else None."""
    if not session.is_open:
        return "No file selected."
    if not opts.sheets:
        return "Please tick at least one sheet to process."
    if opts.layout == "columns" and opts.columns and len(set(opts.columns)) < 3:
        return "X, Y and Z must be three different columns."
    return plot_problem(opts) or folder_problem(opts.output_dir)


def preview_problem(opts: UserOptions) -> Optional[str]:
    """Why the live preview can't be drawn with these options (None if it can)."""
    if opts.layout == "columns" and opts.columns and len(set(opts.columns)) < 3:
        return "X, Y and Z must be three different columns."
    return plot_problem(opts)


def make_run_config(session: DataSession, opts: UserOptions) -> RunConfig:
    fs = opts.font_size
    plot = PlotSettings(
        interpolation=opts.interpolation, grid_resolution=opts.grid_resolution,
        mask_outside_hull=opts.mask_hull, fill_mode=opts.fill_mode, levels=opts.levels,
        level_min=opts.level_min if opts.custom_levels else None,
        level_max=opts.level_max if opts.custom_levels else None,
        level_step=opts.level_step if opts.custom_levels else None,
        cmap=opts.cmap, reverse_cmap=opts.reverse_cmap, show_labels=opts.show_labels,
        label_fontsize=round(fs * 0.8, 1) if fs else 8, show_points=opts.show_points,
        show_grid=opts.show_grid, show_colorbar=opts.show_colorbar, equal_aspect=opts.equal_aspect,
        invert_x=opts.invert_x, invert_y=opts.invert_y, xlim=opts.xlim, ylim=opts.ylim,
        font_size=fs, figsize=(opts.fig_w, opts.fig_h),
        title=opts.title or "", xlabel=opts.xlabel, ylabel=opts.ylabel, cbar_label=opts.cbar_label)
    output = OutputSettings(file_type=opts.file_type, dpi=opts.dpi, transparent=opts.transparent)
    naming = NamingOptions(pattern="{file}_{sheet}" if opts.include_file_name else "{sheet}",
                           prefix=opts.prefix, suffix=opts.suffix, custom_name=opts.custom_name,
                           on_exists=opts.on_exists)
    return RunConfig(
        path=session.path, sheets=list(opts.sheets), output_dir=opts.output_dir,
        load=LoadOptions(header=opts.header, skip_top=opts.skip_top, skip_bottom=opts.skip_bottom),
        layout=opts.layout, columns=opts.columns, column_positions=opts.column_positions,
        plot=plot, output=output, naming=naming)
