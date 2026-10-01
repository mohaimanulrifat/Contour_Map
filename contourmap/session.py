"""Application logic between the GUI and the engine. No tkinter in here.

DataSession   the opened file: cached sheets, preview rows, column guesses
UserOptions   what the user chose in the GUI (plain data, saved/restored per mode)
make_run_config / validate    turn those choices into a RunConfig, or explain what is wrong
"""
import os
import tempfile
from dataclasses import asdict, dataclass, fields, replace
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .data_loader import (DataLoadError, LoadOptions, find_xyz_columns, guess_xyz, list_sheets,
                          load_sheet)
from .engine import FILE_TYPES
from .naming import ON_EXISTS_CHOICES, NamingOptions
from .presets import ModePreset, OutputSettings
from .runner import RunConfig

PREVIEW_ROWS = 20
DPI_CHOICES = (72, 150, 300, 600)


# ------------------------------------------------------------------------------ data session
class DataSession:
    """The currently opened data file."""

    def __init__(self):
        self.path: Optional[str] = None
        self.sheets: List[str] = []
        self.header: bool = True
        self._cache: Dict[Tuple[str, bool], pd.DataFrame] = {}

    @property
    def is_open(self) -> bool:
        return self.path is not None

    def open(self, path: str, header: bool = True) -> None:
        """Open a file. Raises DataLoadError (friendly message) if unusable."""
        sheets = list_sheets(path)
        if not sheets:
            raise DataLoadError("This file contains no sheets.")
        self.path, self.sheets, self.header, self._cache = path, sheets, header, {}
        if len(sheets) == 1:
            df = self.frame(sheets[0])
            if df.shape[1] == 0 or df.empty:
                self.close()
                raise DataLoadError("This file is empty: it has no data rows to plot.")

    def close(self):
        self.path, self.sheets, self._cache = None, [], {}

    def set_header(self, header: bool) -> None:
        if header != self.header:
            self.header = header
            self._cache = {}

    def frame(self, sheet: str) -> pd.DataFrame:
        key = (sheet, self.header)
        if key not in self._cache:
            self._cache[key] = load_sheet(self.path, sheet, LoadOptions(header=self.header))
        return self._cache[key]

    def preview(self, sheet: str, n: int = PREVIEW_ROWS) -> Tuple[List[str], List[List[str]], int]:
        """(column titles, first n rows as strings, total rows)."""
        df = self.frame(sheet)
        rows = [["" if pd.isna(v) else str(v) for v in r] for r in df.head(n).itertuples(index=False)]
        return [str(c) for c in df.columns], rows, len(df)

    def default_labels(self, sheet: str, preset: ModePreset) -> Dict[str, str]:
        """Axis/colorbar texts taken from the column titles of `sheet` ('' if not available)."""
        df = self.frame(sheet)
        if preset.column_mode == "auto_hcp":
            x, y, z, *_ = find_xyz_columns(df)
        else:
            x, y, z = guess_xyz(df)
        return {"xlabel": "" if x is None else str(x), "ylabel": "" if y is None else str(y),
                "cbar_label": "" if z is None else str(z), "title": ""}


# ------------------------------------------------------------------------------ user choices
@dataclass
class UserOptions:
    sheets: List[str]
    output_dir: str = ""
    header: bool = True
    # None = take from the column titles of each sheet; any string (even "") = the user's text
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    cbar_label: Optional[str] = None
    file_type: str = "png"
    dpi: int = 300
    transparent: bool = False
    include_file_name: bool = False
    prefix: str = ""
    suffix: str = ""
    custom_name: str = ""
    on_exists: str = "ask"


# keys kept in the settings file (per mode)
SAVED_KEYS = ("output_dir", "header", "file_type", "dpi", "transparent", "include_file_name",
              "prefix", "suffix", "on_exists")


def to_saved(opts: UserOptions) -> Dict[str, object]:
    d = asdict(opts)
    return {k: d[k] for k in SAVED_KEYS}


def clean_saved(raw: Dict[str, object]) -> Dict[str, object]:
    """Keep only valid saved values, so a hand-edited or old file can't break the GUI."""
    out: Dict[str, object] = {}
    if isinstance(raw.get("output_dir"), str):
        out["output_dir"] = raw["output_dir"]
    for k in ("header", "transparent", "include_file_name"):
        if isinstance(raw.get(k), bool):
            out[k] = raw[k]
    if raw.get("file_type") in FILE_TYPES:
        out["file_type"] = raw["file_type"]
    if raw.get("dpi") in DPI_CHOICES:
        out["dpi"] = raw["dpi"]
    if raw.get("on_exists") in ON_EXISTS_CHOICES:
        out["on_exists"] = raw["on_exists"]
    for k in ("prefix", "suffix"):
        if isinstance(raw.get(k), str):
            out[k] = raw[k]
    return out


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


def validate(preset: ModePreset, session: DataSession, opts: UserOptions) -> Optional[str]:
    """A message for a messagebox if the run can't start, else None."""
    if not session.is_open:
        return "No file selected."
    if not preset.customizable:
        return None
    if not opts.sheets:
        return "Please tick at least one sheet to process."
    return folder_problem(opts.output_dir)


def make_run_config(preset: ModePreset, session: DataSession, opts: UserOptions) -> RunConfig:
    """Build the batch configuration. A non-customizable preset ignores `opts` entirely."""
    if not preset.customizable:
        return RunConfig(path=session.path, preset=preset, sheets=list(session.sheets),
                         output_dir=os.path.dirname(session.path),
                         load=LoadOptions(header=preset.header_row))
    plot = replace(preset.plot, title=opts.title if opts.title is not None else preset.plot.title,
                   xlabel=opts.xlabel, ylabel=opts.ylabel, cbar_label=opts.cbar_label)
    output = OutputSettings(file_type=opts.file_type, dpi=opts.dpi, transparent=opts.transparent,
                            bbox_tight=preset.output.bbox_tight)
    pattern = "{file}_{sheet}" if opts.include_file_name else "{sheet}"
    naming = replace(preset.naming, pattern=pattern, prefix=opts.prefix, suffix=opts.suffix,
                     custom_name=opts.custom_name, on_exists=opts.on_exists)
    return RunConfig(path=session.path, preset=preset, sheets=list(opts.sheets),
                     output_dir=opts.output_dir, load=LoadOptions(header=opts.header),
                     plot=plot, output=output, naming=naming)
