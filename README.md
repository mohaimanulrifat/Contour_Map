# Contour Map Generator

A Windows desktop tool (Python / tkinter) that turns X/Y/Z data in Excel or CSV files into
contour maps. It has a **mode selector**:

| Mode | Purpose |
|---|---|
| **Half Cell Potential** (default) | The original workflow (ASTM C876-15 survey). Locked layout and plot style. |
| **Universal (custom data)** | Any X/Y/Z data with user-chosen columns and plot style. *(arrives in Stage 3)* |

> **Status: Stage 1 of 4.** Mode selector, refactor into modules, and a regression test that proves
> Half Cell Potential output is unchanged. Preview table, naming options, Universal controls,
> live preview and saved settings follow in Stages 2–4.

## Install and run

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python ContourMapApp_GUI.py
```

Dependencies: pandas, numpy, matplotlib, scipy, openpyxl (`.xlsx`) and xlrd (`.xls`).
`xlrd` is the only addition over the original `requirements.txt`: it is small, and without it
`.xls` files cannot be read at all (the original silently relied on it being installed).

## Build the `.exe`

```bat
pip install -r requirements-dev.txt
build.bat
```

This produces `dist\ContourMapApp.exe` (one file, no console). `build.bat` and
`ContourMapApp.spec` both work; both list `openpyxl`, `xlrd` and `scipy.spatial` as hidden
imports. `ContourMapApp_GUI.py` stays the entry point and just starts the `contourmap` package.

## Tests

```bat
pip install -r requirements-dev.txt
python -m pytest
```

## Project layout

```
ContourMapApp_GUI.py      entry point (kept so build.bat / .spec keep working)
contourmap/
  presets.py              ModePreset + PlotSettings dataclasses, one preset per mode
  data_loader.py          reading Excel/CSV, x/y/z column detection, numeric cleaning
  engine.py               interpolation + plotting (matplotlib Figure API, no pyplot)
  naming.py               output file names
  runner.py               one-sheet pipeline and the batch loop (per-sheet error isolation)
  worker.py               background thread + queue + cancel (no tkinter)
  gui.py                  tkinter front end, presentation only
sample_data/              half_cell_sample.xlsx (multi-sheet demo/test data)
tools/make_sample_data.py regenerates the sample workbook
tests/                    regression test + the baseline captured from the original app
```

## Half Cell Potential mode: exactly what the original app did

This section documents the **original** single-file app (initial commit), read from its code.
Half Cell Potential mode reproduces all of it; `tests/test_regression_hcp.py` enforces it.

**Workflow.** Pick a file; the app makes one image per sheet. `.xlsx`/`.xls` → every sheet of the
workbook. `.csv` → treated as one sheet called `Sheet1`.

**Expected sheet layout.**
- Row 1 is the header row. Row 2 onward is data. Header text is whitespace-stripped.
- At least 3 columns, otherwise the sheet is skipped (*"less than 3 columns"*).
- X, Y, Z columns are found by header name, case-insensitive, per axis in this order:
  exactly `x` / `y` / `z`; else a header that *starts with* that letter; else a header containing
  the letter as a separate token, e.g. `Distance (x)`. If the same column would be used for two
  axes, those matches are discarded.
- **If any of X, Y, Z is not found by name, the first three columns are used (X, Y, Z in that
  order)** — for all three, not just the missing one. Extra columns are ignored.
- Values are converted to numbers; anything non-numeric or empty becomes NaN and **the whole row is
  dropped**. If nothing is left the sheet is skipped (*"no numeric x/y/z data"*).

**Interpolation.** `scipy.interpolate.griddata`, method `cubic` (Clough–Tocher on a Delaunay
triangulation), onto a **200 × 200** grid spanning the min/max of the X and Y data
(`np.linspace`). If the cubic result is entirely NaN, or cubic raises, it falls back to `linear`.
Cubic/linear give NaN outside the convex hull of the points, so a non-rectangular survey leaves
blank corners. If linear also fails (e.g. all points on one line) the sheet is reported as an error.

**Plot.**

| Item | Value |
|---|---|
| Figure size | 8 × 7 inches |
| Filled contours | `contourf`, 15 levels, colormap `plasma` |
| Colorbar | label `Corrosion Potential (V)` |
| Contour lines | 15 levels, black, line width 0.5 (negative levels render dashed — matplotlib's default for single-colour lines) |
| Line labels | inline, font size 8, format `%.3f` (e.g. `-0.280`) |
| Title | `Contour Map Based on ASTM C876-15` |
| X / Y axis labels | the exact header text of the X / Y column |
| Grid | on |
| Thresholds | none (the C876 −0.20 / −0.35 V thresholds are **not** drawn; only the title refers to the standard) |

**Output.** PNG, **300 DPI**, `bbox_inches='tight'`. Saved **in the same folder as the input file**
as `<workbook name>_<sheet name>.png`, where every character of the sheet name that is not a
letter, digit, space, `_` or `-` becomes `_` (sheet `Wall (B)` → `half_cell_sample_Wall _B_.png`).
Existing files are overwritten silently.

**What changed in the refactor (on purpose).**
- Each sheet is loaded and processed independently, so one bad sheet can't stop the rest.
- Work runs on a background thread that only posts messages to the GUI (the original updated
  widgets from the worker thread, which tkinter does not support).
- Failures are reported in a results log with the reason; the "collinear points" Qhull dump is
  replaced by a one-line explanation. The sheet still fails exactly as before.
- Plotting uses matplotlib's `Figure` API instead of `pyplot`, so nothing leaks between sheets.
- CSV files now get delimiter/encoding auto-detection (a plain UTF-8 comma CSV reads identically).

### Regression test

`tests/baseline/` holds a byte-for-byte copy of the original script and the output it produced for
`sample_data/half_cell_sample.xlsx` (images, interpolated grids, contour levels, labels, which
sheets were skipped/failed). `generate_baseline.py` re-creates that baseline by executing the
**original** code headlessly; it is not part of the normal test run. The test checks, in order:
saved file names → numeric grids and levels → title/labels/figure size/line labels →
PNG pixels (exact when matplotlib's version matches the baseline's, otherwise a tiny tolerance).

## Adding a new mode (a new test type)

A mode is a `ModePreset` in `contourmap/presets.py`: default `PlotSettings` (colormap, levels,
labels, figure size…), `OutputSettings`, `column_mode` (`"auto_hcp"` rule or `"user"` picks),
the default file-name pattern, and which GUI sections to show. Add it to the `MODES` dict and it
appears in the dropdown; the engine and GUI need no changes.
