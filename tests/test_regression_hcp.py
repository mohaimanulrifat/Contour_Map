"""Regression: Half Cell Potential mode must reproduce the ORIGINAL app's output.

The expected files in tests/baseline/ were produced by running the original,
unmodified code (see tests/baseline/generate_baseline.py). Four layers of checks:

  1. which sheets are saved / skipped / failed, and the file names
  2. the interpolated X/Y/Z grids and contour levels (numeric, tight tolerance)
  3. title, axis/colorbar labels, figure size, contour-label texts, savefig dpi
  4. the saved PNG pixels (exact when matplotlib matches the baseline's version,
     otherwise a small tolerance because font rendering can differ between versions)
"""
import json
import os
import shutil

import matplotlib
import matplotlib.image as mpimg
import numpy as np
import pytest

from contourmap.data_loader import load_sheet
from contourmap.presets import HALF_CELL
from contourmap.runner import RunConfig, build_sheet_figure, run_batch
from contourmap.data_loader import list_sheets

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "baseline")
SAMPLE = os.path.join(HERE, "..", "sample_data", "half_cell_sample.xlsx")

with open(os.path.join(BASE, "expected_meta.json"), encoding="utf-8") as fh:
    META = json.load(fh)
ARRAYS = np.load(os.path.join(BASE, "expected_arrays.npz"))
SAME_MPL = META["generated_with"]["matplotlib"] == matplotlib.__version__


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("hcp_out")
    # the original saved next to the input file, so mimic that
    src = out / META["input_file"]
    shutil.copy(SAMPLE, src)
    cfg = RunConfig(path=str(src), preset=HALF_CELL, sheets=list_sheets(str(src)),
                    output_dir=str(out))
    results = run_batch(cfg)
    return cfg, results, out


def test_same_sheets_saved_with_same_file_names(run):
    _, results, out = run
    saved = [os.path.basename(r.path) for r in results if r.status == "saved"]
    assert saved == [m["file"] for m in META["plotted"]]
    for name in saved:
        assert (out / name).exists()


def test_skipped_and_failed_sheets_match_original(run):
    _, results, _ = run
    by = {r.sheet: r for r in results}
    msgs = " | ".join(META["status_messages"])
    # original: "Skipped: Two Columns (less than 3 columns)"
    assert by["Two Columns"].status == "skipped" and "less than 3 columns" in msgs
    assert by["Notes only"].status == "skipped" and "no numeric x/y/z data" in msgs
    # original: "Error in Collinear: ..." (the sheet failed, others carried on)
    assert by["Collinear"].status == "error" and "Error in Collinear" in msgs
    assert len([r for r in results if r.status == "saved"]) == len(META["plotted"])


def _plotted():
    return list(enumerate(META["plotted"]))


@pytest.mark.parametrize("idx,meta", _plotted(), ids=[m["file"] for _, m in _plotted()])
def test_grids_levels_and_labels(run, idx, meta):
    cfg, _, _ = run
    sheet = meta["file"][len("half_cell_sample_"):-len(".png")]
    # sheet names are sanitised in the file name; map back via the workbook's sheet list
    sheet = next(s for s in cfg.sheets if "".join(c if c.isalnum() or c in " _-" else "_" for c in s) == sheet)
    df = load_sheet(cfg.path, sheet, cfg.load)
    result, _, _ = build_sheet_figure(df, cfg)

    np.testing.assert_allclose(result.grid.X, ARRAYS[f"{idx}_X"], rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.grid.Y, ARRAYS[f"{idx}_Y"], rtol=1e-12, atol=0)
    np.testing.assert_allclose(result.grid.Z, ARRAYS[f"{idx}_Z"], rtol=1e-9, atol=1e-12,
                               equal_nan=True)
    np.testing.assert_allclose(result.filled.levels, ARRAYS[f"{idx}_levels"], rtol=1e-12)
    np.testing.assert_allclose(result.lines.levels, meta["line_levels"], rtol=1e-12)

    fig = result.figure
    ax, cax = fig.axes[0], fig.axes[1]
    assert ax.get_title() == meta["title"]
    assert ax.get_xlabel() == meta["xlabel"]
    assert ax.get_ylabel() == meta["ylabel"]
    assert cax.get_ylabel() == meta["cbar_label"]
    assert list(fig.get_size_inches()) == meta["figsize"]
    assert [t.get_text() for t in ax.texts] == meta["label_texts"]


@pytest.mark.parametrize("meta", META["plotted"], ids=[m["file"] for m in META["plotted"]])
def test_png_pixels(run, meta):
    _, _, out = run
    new = mpimg.imread(str(out / meta["file"]))
    old = mpimg.imread(os.path.join(BASE, "expected", meta["file"]))
    assert new.shape == old.shape, "image size changed (dpi / figsize / bbox)"
    if SAME_MPL:
        np.testing.assert_array_equal(new, old)
    else:  # different matplotlib: allow tiny text-rendering differences
        assert np.abs(new - old).mean() < 0.01


def test_hcp_preset_is_locked_to_original_style():
    p = HALF_CELL.plot
    assert (p.interpolation, p.grid_resolution, p.levels, p.cmap) == ("cubic", 200, 15, "plasma")
    assert (p.line_color, p.line_width, p.label_fontsize, p.label_format) == ("k", 0.5, 8, "%.3f")
    assert p.figsize == (8, 7) and p.show_grid and p.show_labels and p.fill_mode == "both"
    assert p.title == "Contour Map Based on ASTM C876-15"
    assert p.cbar_label == "Corrosion Potential (V)"
    assert (HALF_CELL.output.dpi, HALF_CELL.output.file_type, HALF_CELL.output.bbox_tight) == (300, "png", True)
