"""Batch processing: turn selected sheets into images. GUI-free; safe to run in a thread.

The GUI builds a RunConfig and calls run_batch() on a worker thread, passing callbacks that
only put messages on a queue. One failing sheet never stops the others.
"""
import os
import threading
from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Tuple

import pandas as pd

from . import naming
from .data_loader import (GRID_COLUMNS, DataLoadError, LoadOptions, SheetSkipped, XYZData,
                          extract_xyz, grid_to_xyz, guess_xyz, load_sheet)
from .defaults import DEFAULT_OUTPUT, DEFAULT_PLOT, OutputSettings, PlotSettings
from .engine import PlotError, RenderResult, render_figure, save_figure
from .naming import NamingOptions

LAYOUTS = ("columns", "grid")


@dataclass
class RunConfig:
    path: str                              # input data file
    sheets: List[str]                      # sheets to process, in order
    output_dir: str
    load: LoadOptions = LoadOptions()
    layout: str = "columns"                # "columns" (X, Y, Z columns) | "grid" (matrix)
    # Chosen X/Y/Z columns. None = guess per sheet. `column_positions` (indices in the sheet the
    # user looked at) are the fallback for sheets that don't have those column names.
    columns: Optional[Tuple[str, str, str]] = None
    column_positions: Optional[Tuple[int, int, int]] = None
    plot: PlotSettings = DEFAULT_PLOT
    output: OutputSettings = DEFAULT_OUTPUT
    naming: NamingOptions = NamingOptions()


@dataclass
class SheetResult:
    sheet: str
    status: str                            # "saved" | "skipped" | "error"
    message: str = ""
    path: Optional[str] = None
    info: str = ""                         # e.g. "52 valid points of 55 rows (3 dropped)"


def load_options_for(cfg: RunConfig) -> LoadOptions:
    """Grid layout is always read without a header row (row 1 holds the X values)."""
    return replace(cfg.load, header=False) if cfg.layout == "grid" else cfg.load


def prepare_frame(df: pd.DataFrame, layout: str, columns=None, positions=None
                  ) -> Tuple[pd.DataFrame, Tuple[str, str, str], str]:
    """The table to extract from, the X/Y/Z column names in it, and a note for the log.

    Raises SheetSkipped if this sheet cannot be used.
    """
    if layout == "grid":
        return grid_to_xyz(df), GRID_COLUMNS, ""
    if df.empty:
        raise SheetSkipped("sheet is empty")
    note = ""
    if not columns:
        cols = guess_xyz(df)
        if None in cols:
            raise SheetSkipped("needs at least 3 columns to use as X, Y and Z")
        note = "columns chosen automatically"
    elif all(c in df.columns for c in columns):
        cols = tuple(columns)
    elif positions and all(p < df.shape[1] for p in positions):
        cols = tuple(df.columns[p] for p in positions)
        note = "column names not found, used the same column positions"
    else:
        missing = [str(c) for c in columns if c not in df.columns]
        raise SheetSkipped(f"column(s) not found: {', '.join(missing)}")
    if len(set(cols)) < 3:
        raise SheetSkipped("X, Y and Z must be three different columns")
    return df, cols, note


def build_sheet_figure(df: pd.DataFrame, cfg: RunConfig
                       ) -> Tuple[RenderResult, XYZData, Tuple[str, str, str], str]:
    """Everything between 'DataFrame in' and 'Figure out'. Also used by the live preview."""
    frame, (x_col, y_col, z_col), note = prepare_frame(df, cfg.layout, cfg.columns, cfg.column_positions)
    data = extract_xyz(frame, x_col, y_col, z_col)
    if len(data.x) == 0:
        raise SheetSkipped("no numeric X/Y/Z data")
    s = cfg.plot
    s = replace(
        s,
        xlabel=s.xlabel if s.xlabel is not None else str(x_col),
        ylabel=s.ylabel if s.ylabel is not None else str(y_col),
        cbar_label=s.cbar_label if s.cbar_label is not None else str(z_col),
    )
    return render_figure(data.x, data.y, data.z, s), data, (x_col, y_col, z_col), note


def process_sheet(cfg: RunConfig, sheet: str, used: Optional[set] = None,
                  ask: Callable[[str], str] = lambda path: "number") -> SheetResult:
    used = set() if used is None else used
    try:
        df = load_sheet(cfg.path, sheet, load_options_for(cfg))
        result, data, _, note = build_sheet_figure(df, cfg)
        base = os.path.splitext(os.path.basename(cfg.path))[0]
        name = naming.build_basename(cfg.naming, base, sheet, single_sheet=len(cfg.sheets) == 1)
        path = naming.resolve_path(cfg.output_dir, name, cfg.output.file_type, cfg.naming, used, ask)
        if path is None:
            return SheetResult(sheet, "skipped", "file already exists (skipped)")
        save_figure(result.figure, path, cfg.output)
        used.add(path)
        notes = [data.summary()] + ([note] if note else []) + result.grid.notes
        return SheetResult(sheet, "saved", path=path, info="; ".join(notes))
    except SheetSkipped as e:
        return SheetResult(sheet, "skipped", str(e))
    except (PlotError, DataLoadError) as e:
        return SheetResult(sheet, "error", str(e).strip())
    except Exception as e:                    # never let one sheet stop the batch
        return SheetResult(sheet, "error", f"{type(e).__name__}: {str(e).strip()}")


def run_batch(cfg: RunConfig,
              on_progress: Callable[[int, int, str], None] = lambda i, n, sheet: None,
              on_result: Callable[[SheetResult], None] = lambda r: None,
              cancel: Optional[threading.Event] = None,
              ask_overwrite: Callable[[str], str] = lambda path: "number") -> List[SheetResult]:
    """Process every sheet in cfg.sheets. Returns the results actually produced.

    ask_overwrite(path) is called when naming.on_exists == "ask" and a file exists; it returns
    "overwrite", "number" or "skip".
    """
    cancel = cancel or threading.Event()
    results: List[SheetResult] = []
    used: set = set()
    total = len(cfg.sheets)
    for i, sheet in enumerate(cfg.sheets, start=1):
        if cancel.is_set():
            break
        on_progress(i, total, sheet)
        res = process_sheet(cfg, sheet, used, ask_overwrite)
        results.append(res)
        on_result(res)
    return results
