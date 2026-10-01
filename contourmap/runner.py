"""Batch processing: turn selected sheets into images. GUI-free; safe to run in a thread.

The GUI builds a RunConfig and calls run_batch() on a worker thread, passing callbacks that
only put messages on a queue. One failing sheet never stops the others.
"""
import os
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import pandas as pd

from . import naming
from .data_loader import (DataLoadError, LoadOptions, SheetSkipped, XYZData, extract_xyz,
                          find_xyz_columns, load_sheet)
from .engine import PlotError, RenderResult, render_figure, save_figure
from .presets import ModePreset, OutputSettings, PlotSettings
from dataclasses import replace


@dataclass
class RunConfig:
    path: str                              # input data file
    preset: ModePreset
    sheets: List[str]                      # sheets to process, in order
    output_dir: str
    load: LoadOptions = LoadOptions()
    plot: Optional[PlotSettings] = None    # None -> preset.plot
    output: Optional[OutputSettings] = None
    columns: Optional[Tuple[str, str, str]] = None   # user-picked (x, y, z); None -> preset rule

    def __post_init__(self):
        if self.plot is None:
            self.plot = self.preset.plot
        if self.output is None:
            self.output = self.preset.output


@dataclass
class SheetResult:
    sheet: str
    status: str                            # "saved" | "skipped" | "error"
    message: str = ""
    path: Optional[str] = None
    info: str = ""                         # e.g. "52 valid points of 55 rows (3 dropped)"


def pick_columns(df: pd.DataFrame, cfg: RunConfig) -> Tuple[str, str, str]:
    """Which columns are X, Y, Z for this sheet. Raises SheetSkipped if it cannot be decided."""
    if cfg.preset.column_mode == "auto_hcp":
        if df.shape[1] < 3:
            raise SheetSkipped("less than 3 columns")
        x_col, y_col, z_col, *_ = find_xyz_columns(df)
        if x_col is None or y_col is None or z_col is None:
            raise SheetSkipped("couldn't determine x,y,z")
        return x_col, y_col, z_col
    if not cfg.columns:
        raise SheetSkipped("no X/Y/Z columns selected")
    missing = [c for c in cfg.columns if c not in df.columns]
    if missing:
        raise SheetSkipped(f"column(s) not found: {', '.join(map(str, missing))}")
    return cfg.columns


def build_sheet_figure(df: pd.DataFrame, cfg: RunConfig) -> Tuple[RenderResult, XYZData, Tuple[str, str, str]]:
    """Everything between 'DataFrame in' and 'Figure out'. Also used by the live preview."""
    x_col, y_col, z_col = pick_columns(df, cfg)
    data = extract_xyz(df, x_col, y_col, z_col)
    if len(data.x) == 0:
        raise SheetSkipped("no numeric x/y/z data")
    s = cfg.plot
    s = replace(
        s,
        xlabel=s.xlabel if s.xlabel is not None else str(x_col),
        ylabel=s.ylabel if s.ylabel is not None else str(y_col),
        cbar_label=s.cbar_label if s.cbar_label is not None else str(z_col),
    )
    result = render_figure(data.x, data.y, data.z, s)
    return result, data, (x_col, y_col, z_col)


def output_path(cfg: RunConfig, sheet: str) -> str:
    base = os.path.splitext(os.path.basename(cfg.path))[0]
    return os.path.join(cfg.output_dir, naming.legacy_filename(base, sheet, cfg.output.file_type))


def process_sheet(cfg: RunConfig, sheet: str) -> SheetResult:
    try:
        df = load_sheet(cfg.path, sheet, cfg.load)
        result, data, _ = build_sheet_figure(df, cfg)
        path = output_path(cfg, sheet)
        save_figure(result.figure, path, cfg.output)
        info = data.summary()
        if result.grid.notes:
            info += "; " + "; ".join(result.grid.notes)
        return SheetResult(sheet, "saved", path=path, info=info)
    except SheetSkipped as e:
        return SheetResult(sheet, "skipped", str(e))
    except (PlotError, DataLoadError) as e:
        return SheetResult(sheet, "error", str(e).strip())
    except Exception as e:                    # never let one sheet stop the batch
        return SheetResult(sheet, "error", f"{type(e).__name__}: {str(e).strip()}")


def run_batch(cfg: RunConfig,
              on_progress: Callable[[int, int, str], None] = lambda i, n, sheet: None,
              on_result: Callable[[SheetResult], None] = lambda r: None,
              cancel: Optional[threading.Event] = None) -> List[SheetResult]:
    """Process every sheet in cfg.sheets. Returns the results actually produced."""
    cancel = cancel or threading.Event()
    results: List[SheetResult] = []
    total = len(cfg.sheets)
    for i, sheet in enumerate(cfg.sheets, start=1):
        if cancel.is_set():
            break
        on_progress(i, total, sheet)
        res = process_sheet(cfg, sheet)
        results.append(res)
        on_result(res)
    return results
