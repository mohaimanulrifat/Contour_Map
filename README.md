# Contour Map Generator

A Windows desktop tool (Python / tkinter) that turns X/Y/Z data from Excel, CSV or text files
into contour maps: one image per sheet, with full control over columns, interpolation, styling
and file output.

> **Status: Stage 3 of 4.** Data options, column pickers, grid layout, all plot settings, labels,
> multi-sheet output and file naming are in. Still to come in Stage 4: live map preview inside the
> window, and final polish.

## Install and run

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python ContourMapApp_GUI.py
```

Dependencies: pandas, numpy, matplotlib, scipy, openpyxl (`.xlsx`), xlrd (`.xls`). Pillow comes
with matplotlib and is used for the logo and the checkbox graphics.

## Using it

1. **Open file…** (`.xlsx`, `.xls`, `.csv`, `.txt`). CSV/TXT delimiter (comma, semicolon, tab,
   pipe, spaces), encoding (UTF-8 / Windows-1252) and European decimal commas are detected
   automatically. The **Data preview** shows the first 20 rows of the sheet chosen in *Sheet*.
2. Work through the tabs on the left, then press **Generate maps**.
3. The progress bar shows `Sheet 2 of 5: name…`; **Cancel** stops after the sheet being drawn.
   The **Results** box lists every file saved and every sheet skipped or failed, with the reason.
   One bad sheet never stops the others.

### 01 Data
| Option | Meaning |
|---|---|
| **Column format** | Each row is one point; pick the X, Y and Z columns. |
| **Grid / matrix format** | Row headers = Y values, column headers = X values, cells = Z (the top-left corner cell is ignored). |
| **Use first row as column titles** | On: row 1 names the columns. Off: columns are called `Column 1`, `Column 2`… The preview updates immediately. (Not used for grid format.) |
| **Skip rows at top / Ignore rows at bottom** | Ignore title lines above, or totals below, the table. |
| **Columns X / Y / Z** | Pre-selected automatically (columns named x/y/z, otherwise the first three numeric columns). Change them in the dropdowns. A line underneath shows how many valid points were found and how many empty / non-numeric rows would be dropped. |
| **Sheets to process** | *Process all sheets*, or tick the ones you want. If you changed the columns and a sheet doesn't have those column names, the same column *positions* are used (the log says so). |

### 02 Plot
Interpolation (linear, cubic, nearest; cubic falls back to linear when the data can't support it)
· grid resolution · mask outside the data hull · Filled / Lines / Both · number of levels or
custom min/max/step · colormap (with preview strip) and reverse · contour labels, data points,
grid lines, colorbar · equal aspect ratio · invert X / Y · axis limits · font size · figure size.

### 03 Labels
Plot title, X axis name, Y axis name, colorbar label. Pre-filled from the column titles; a box you
edit applies to every sheet, boxes you don't touch follow each sheet's own titles.

### 04 Output
Folder (remembered), file type **PNG / JPG / PDF / SVG / TIFF**, DPI **72 / 150 / 300 / 600**,
transparent background (not for JPG).
File names: default is the **sheet name**; optionally put the data file name first, add a
prefix/suffix, or give a custom name (only when a single sheet is processed). Characters Windows
doesn't allow (`< > : " / \ | ? *`), reserved names such as `CON`, and trailing dots/spaces are
replaced or removed. If a file exists: **Ask me** (overwrite / new number / skip), **Add a number**
(`name (1).png`) or **Overwrite**. Two sheets that would get the same name in one run are always
numbered, never overwritten.

### Remembered settings
Output folder, file type, DPI, layout, header choice, naming options and all plot options are saved
to `contour_settings.json` next to the app (or `%APPDATA%\ContourMapApp` if that folder isn't
writable) and restored on the next start. Delete the file to reset. It is ignored by git.

## Your name and logo

Put `logo.png` in `assets/` and set `APP_NAME` / `APP_TAGLINE` in `contourmap/branding.py`.
Replace `contour.ico` for the window/exe icon. With no logo the header just shows the name.
The look (deep indigo, violet accents, Inter type) lives in `contourmap/theme.py`; Inter is
bundled in `assets/fonts` (SIL Open Font License) and falls back to Segoe UI.

## Build the `.exe`

```bat
pip install -r requirements-dev.txt
build.bat
```

Produces `dist\ContourMapApp.exe` (one file, no console). `build.bat` and `ContourMapApp.spec`
are equivalent; both bundle `assets/` and `contour.ico` and list the hidden imports
(`openpyxl`, `xlrd`, `scipy.spatial`, `PIL._tkinter_finder`).

## Tests

```bat
python -m pytest
```

Covers data loading (delimiters, encodings, skip rows, grid conversion), interpolation and
plotting options, file naming, option validation, batch runs and settings. The GUI tests drive the
real window and are skipped automatically where no display is available.

## Project layout

```
ContourMapApp_GUI.py      entry point (kept so build.bat / .spec keep working)
contourmap/
  branding.py             app name, tagline, logo and icon lookup
  theme.py                colours, fonts, ttk styling, custom widgets (cards, pill buttons, tabs)
  gui.py                  the window; presentation only
  session.py              opened file, previews, column checks, user options -> run config, validation
  runner.py               one-sheet pipeline and the batch loop (per-sheet error isolation)
  worker.py               background thread + queue + cancel (no tkinter)
  data_loader.py          Excel/CSV/TXT reading, grid conversion, numeric cleaning
  engine.py               interpolation + plotting (matplotlib Figure API, no pyplot)
  defaults.py             PlotSettings / OutputSettings and their defaults
  naming.py               file-name building, sanitising, overwrite / numbering
  settings.py             last-used settings JSON
sample_data/              sample_multisheet.xlsx (9 sheets) and sample_scattered.csv
tools/make_sample_data.py regenerates the sample files
tests/                    unit and GUI tests
assets/                   logo (yours), fonts
```

The sample workbook includes sheets that exercise each situation: regular and scattered points,
a text column, dirty values, title/footer rows (use skip rows `2` / `2`), a matrix sheet (use grid
layout), and sheets that are skipped or fail on purpose (2 columns, text only, collinear points).
