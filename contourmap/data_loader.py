"""Data loading and column handling. No GUI and no plotting in here."""
import csv
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

EXCEL_EXTS = (".xlsx", ".xlsm", ".xls")
TEXT_EXTS = (".csv", ".txt")
SUPPORTED_EXTS = EXCEL_EXTS + TEXT_EXTS
CSV_SHEET_NAME = "Sheet1"      # a CSV/TXT file is treated as a single sheet with this name


class DataLoadError(Exception):
    """The file could not be read (message is safe to show to the user)."""


class SheetSkipped(Exception):
    """A sheet has no usable data (not an error: reported as 'skipped')."""


@dataclass(frozen=True)
class LoadOptions:
    header: bool = True          # first row holds the column titles
    skip_top: int = 0            # rows ignored at the top of every sheet
    skip_bottom: int = 0         # rows ignored at the bottom of every sheet
    encoding: Optional[str] = None   # None = auto-detect (text files)
    delimiter: Optional[str] = None  # None = auto-detect (text files)


# ----------------------------------------------------------------------------- reading
def _check_ext(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise DataLoadError(
            f"Unsupported file type '{ext or path}'.\nSupported: {', '.join(SUPPORTED_EXTS)}")
    return ext


def detect_encoding(path: str) -> str:
    """UTF-8 (with or without BOM) if the file decodes as such, else Windows-1252."""
    raw = open(path, "rb").read(1 << 20)
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        raw.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError:
        # a multi-byte char cut off at the sample boundary is not a real error
        try:
            raw[:-3].decode("utf-8")
            return "utf-8-sig"
        except UnicodeDecodeError:
            return "cp1252"


_CANDIDATES = (",", ";", "\t", "|")
_WHITESPACE = r"\s+"


def _field_counts(lines: List[str], delim: str) -> List[int]:
    if delim == _WHITESPACE:
        return [len(ln.split()) for ln in lines]
    counts = []
    for ln in lines:
        try:
            counts.append(len(next(csv.reader([ln], delimiter=delim))))
        except (csv.Error, StopIteration):
            counts.append(1)
    return counts


def _score(counts: List[int]) -> Tuple[int, int]:
    """(how many lines agree on the most common field count, that count); 0 if it is 1 column."""
    if not counts:
        return (0, 0)
    modal, agree = Counter(counts).most_common(1)[0]
    return (agree, modal) if modal > 1 else (0, 0)


def _sample_lines(path: str, encoding: str, skip_top: int) -> List[str]:
    with open(path, "r", encoding=encoding, errors="replace", newline="") as fh:
        sample = fh.read(64 * 1024)
    return [ln for ln in sample.splitlines()[skip_top:] if ln.strip()][:50]


def detect_delimiter(path: str, encoding: str, skip_top: int = 0) -> str:
    """Delimiter of a text file: the one that splits most lines into the same number of fields.

    Lines above the table (titles) don't matter as long as most lines agree, and the first
    `skip_top` lines are ignored altogether.
    """
    lines = _sample_lines(path, encoding, skip_top)
    best, best_score = ",", (0, 0)
    for d in _CANDIDATES:
        sc = _score(_field_counts(lines, d))
        if sc > best_score:
            best, best_score = d, sc
    if best_score == (0, 0):
        ws = _score(_field_counts(lines, _WHITESPACE))
        if ws[0] >= max(2, len(lines) // 2):
            return _WHITESPACE
    return best


def _finish(df: pd.DataFrame, opts: LoadOptions) -> pd.DataFrame:
    """Apply skip_bottom and normalise column names (strip whitespace; Column 1.. if no header)."""
    if opts.skip_bottom > 0:
        df = df.iloc[:-opts.skip_bottom] if opts.skip_bottom < len(df) else df.iloc[0:0]
    if opts.header:
        df.columns = [str(c).strip() for c in df.columns]
    else:
        df.columns = [f"Column {i}" for i in range(1, df.shape[1] + 1)]
    return df.reset_index(drop=True)


def _to_numeric_if_possible(col: pd.Series) -> pd.Series:
    try:
        return pd.to_numeric(col)
    except (ValueError, TypeError):
        return col


def _promote_header(df: pd.DataFrame) -> pd.DataFrame:
    """Use the first row as column titles (for tables read without a header)."""
    if df.empty:
        return df
    titles = [str(t).strip() if pd.notna(t) else f"Unnamed: {i}" for i, t in enumerate(df.iloc[0])]
    body = df.iloc[1:].reset_index(drop=True)
    body.columns = titles
    return body.apply(_to_numeric_if_possible)


def _read_text(path: str, opts: LoadOptions) -> pd.DataFrame:
    enc = opts.encoding or detect_encoding(path)
    delim = opts.delimiter or detect_delimiter(path, enc, opts.skip_top)
    kwargs = dict(encoding=enc, skiprows=opts.skip_top or None, sep=delim)
    if len(delim) > 1:
        kwargs["engine"] = "python"
    lines = _sample_lines(path, enc, opts.skip_top)
    if delim == ";" and any(re.search(r"\d,\d", ln) for ln in lines[1:]):
        kwargs["decimal"] = ","            # European style: 1,5 means 1.5
    counts = _field_counts(lines, delim)
    ragged = bool(counts) and counts[0] < max(counts)
    try:
        if ragged:
            # a title line shorter than the table: give pandas the full width so it can't choke
            df = pd.read_csv(path, header=None, names=list(range(max(counts))), **kwargs)
            return _promote_header(df) if opts.header else df
        return pd.read_csv(path, header=0 if opts.header else None, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except UnicodeDecodeError as e:
        raise DataLoadError(f"Could not decode the file with encoding '{enc}': {e}")
    except pd.errors.ParserError as e:
        raise DataLoadError(f"The text file could not be split into columns:\n{e}")


def list_sheets(path: str) -> List[str]:
    """Sheet names of a file (a text file has one sheet called 'Sheet1')."""
    ext = _check_ext(path)
    if ext in TEXT_EXTS:
        return [CSV_SHEET_NAME]
    try:
        with pd.ExcelFile(path) as xls:
            return list(xls.sheet_names)
    except ImportError as e:
        raise DataLoadError(f"A library needed to read this file is missing:\n{e}")
    except Exception as e:
        raise DataLoadError(f"Could not open the Excel file:\n{e}")


def load_sheet(path: str, sheet: str, opts: LoadOptions = LoadOptions()) -> pd.DataFrame:
    """Load one sheet as a DataFrame with cleaned column names."""
    ext = _check_ext(path)
    try:
        if ext in TEXT_EXTS:
            df = _read_text(path, opts)
        else:
            with pd.ExcelFile(path) as xls:
                df = xls.parse(sheet, header=0 if opts.header else None,
                               skiprows=opts.skip_top or None)
    except DataLoadError:
        raise
    except ImportError as e:
        raise DataLoadError(f"A library needed to read this file is missing:\n{e}")
    except Exception as e:
        raise DataLoadError(f"Problem reading '{sheet}':\n{e}")
    return _finish(df, opts)


def load_all(path: str, opts: LoadOptions = LoadOptions()) -> Dict[str, pd.DataFrame]:
    """Load every sheet. Raises DataLoadError if the file cannot be opened at all."""
    return {name: load_sheet(path, name, opts) for name in list_sheets(path)}


# ----------------------------------------------------------------------------- columns
def find_xyz_columns(df):
    """
    Try to locate x, y, z columns in dataframe by name (case-insensitive).
    If names are not found, fall back to first 3 columns (by position).
    Returns (x_col_name, y_col_name, z_col_name, label_x, label_y, label_z)
    where label_* are the strings to use for axis/colorbar (header text).

    Used to pre-select the column dropdowns.
    """
    cols = list(df.columns)
    lower = [str(c).strip().lower() for c in cols]

    # match rules: exact 'x','y','z' or startswith 'x', 'y', 'z', or contains ' x' or 'x ' or '(x)'
    def match_index(prefix):
        for i, name in enumerate(lower):
            if name == prefix:
                return i
        for i, name in enumerate(lower):
            if name.startswith(prefix):
                return i
        # also look for patterns like '(x)', ' x)', ' x '
        pattern = re.compile(r'(^|[^a-z0-9])' + re.escape(prefix) + r'([^a-z0-9]|$)')
        for i, name in enumerate(lower):
            if pattern.search(name):
                return i
        return None

    xi = match_index('x')
    yi = match_index('y')
    zi = match_index('z')

    # Avoid duplicates: if matched same column for multiple axes, discard those matches
    if xi is not None and yi is not None and xi == yi:
        yi = None
    if xi is not None and zi is not None and xi == zi:
        zi = None
    if yi is not None and zi is not None and yi == zi:
        zi = None

    # Fallback: use first 3 columns by position if any of xi,yi,zi is None
    if xi is None or yi is None or zi is None:
        if len(cols) >= 3:
            x_col, y_col, z_col = cols[0], cols[1], cols[2]
        else:
            # not enough columns
            return (None, None, None, None, None, None)
    else:
        x_col, y_col, z_col = cols[xi], cols[yi], cols[zi]

    # Labels will be the header strings (exact text)
    label_x = str(x_col)
    label_y = str(y_col)
    label_z = str(z_col)
    return (x_col, y_col, z_col, label_x, label_y, label_z)


def numeric_columns(df: pd.DataFrame, min_fraction: float = 0.5) -> List[str]:
    """Columns where at least `min_fraction` of the non-empty cells are numbers."""
    out = []
    for c in df.columns:
        col = df[c]
        nonempty = col.notna().sum()
        if nonempty and pd.to_numeric(col, errors="coerce").notna().sum() / nonempty >= min_fraction:
            out.append(c)
    return out


def guess_xyz(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Best-guess (x, y, z) for the dropdowns: columns named x/y/z, else the first 3 numeric columns."""
    x, y, z, *_ = find_xyz_columns(df)
    if x is not None:
        by_name = [c for c in (x, y, z) if c in numeric_columns(df)]
        if len(by_name) == 3:
            return x, y, z
    nums = numeric_columns(df)
    nums += [c for c in df.columns if c not in nums]
    nums = nums[:3] + [None] * (3 - len(nums[:3]))
    return nums[0], nums[1], nums[2]


GRID_COLUMNS = ("X", "Y", "Z")


def grid_to_xyz(df: pd.DataFrame) -> pd.DataFrame:
    """Matrix layout -> long X/Y/Z table.

    `df` must be read without a header row: the first row holds the X values (column headers),
    the first column holds the Y values (row headers) and the remaining cells are Z. The corner
    cell is ignored. Values are left as read; extract_xyz() validates them and counts the drops.
    """
    if df.shape[0] < 2 or df.shape[1] < 2:
        raise SheetSkipped("grid layout needs a header row, a header column and at least one cell")
    xs = df.iloc[0, 1:].to_numpy(dtype=object)
    ys = df.iloc[1:, 0].to_numpy(dtype=object)
    cells = df.iloc[1:, 1:].to_numpy(dtype=object)
    return pd.DataFrame({
        "X": np.tile(xs, len(ys)),          # x varies fastest, matching row-major cells.ravel()
        "Y": np.repeat(ys, len(xs)),
        "Z": cells.ravel(),
    })


# ----------------------------------------------------------------------------- numeric extraction
@dataclass(frozen=True)
class XYZData:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    n_rows: int           # rows examined
    n_empty: int          # rows dropped because a value was blank
    n_nonnumeric: int     # rows dropped because a value was text / not a number

    @property
    def n_dropped(self) -> int:
        return self.n_empty + self.n_nonnumeric

    def summary(self) -> str:
        s = f"{len(self.x)} valid points of {self.n_rows} rows"
        if self.n_dropped:
            s += f" ({self.n_empty} empty and {self.n_nonnumeric} non-numeric rows dropped)"
        return s


def extract_xyz(df: pd.DataFrame, x_col, y_col, z_col) -> XYZData:
    """Coerce three columns to numbers and drop rows with any empty / non-numeric value."""
    cols = {"x": x_col, "y": y_col, "z": z_col}
    raw = pd.DataFrame({k: df[c] for k, c in cols.items()})
    num = raw.apply(lambda s: pd.to_numeric(s, errors="coerce"))
    bad = num.isna().any(axis=1)
    nonnumeric = (num.isna() & raw.notna()).any(axis=1)
    clean = num.dropna()
    return XYZData(
        x=clean["x"].values, y=clean["y"].values, z=clean["z"].values,
        n_rows=len(raw),
        n_empty=int((bad & ~nonnumeric).sum()),
        n_nonnumeric=int(nonnumeric.sum()),
    )
