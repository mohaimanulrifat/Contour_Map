import os

import pytest

from contourmap.data_loader import DataLoadError
from contourmap.runner import build_sheet_figure, run_batch
from contourmap.data_loader import load_sheet
from contourmap.session import (DataSession, OptionError, UserOptions, clean_saved, folder_problem,
                                make_run_config, parse_float, parse_int, plot_problem, to_saved,
                                validate)
from contourmap.settings import SettingsStore

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "sample_multisheet.xlsx")


@pytest.fixture
def session():
    s = DataSession()
    s.open(SAMPLE)
    return s


def opts(tmp_path, sheets=("Survey A",), **kw):
    return UserOptions(sheets=list(sheets), output_dir=str(tmp_path), **kw)


def test_preview_limits_rows_and_keeps_all_columns(session):
    cols, rows, total = session.preview("Survey C")
    assert cols == ["Distance (m)", "Height (m)", "Reading (V)", "Notes"]
    assert len(rows) == 20 and total == 30


def test_header_toggle_renames_columns(session):
    session.set_reading(False, 0, 0, "columns")
    cols, rows, total = session.preview("Survey A")
    assert cols == ["Column 1", "Column 2", "Column 3"] and total == 64
    session.set_reading(True, 0, 0, "columns")
    assert session.preview("Survey A")[0][0] == "X (m)"


def test_skip_rows_top_and_bottom(session):
    session.set_reading(True, 2, 2, "columns")
    cols, _, total = session.preview("Padded")
    assert cols == ["x", "y", "z"] and total == 20
    assert session.check("Padded") == (True, "20 valid points of 20 rows")


def test_grid_layout_preview_and_check(session):
    session.set_reading(True, 0, 0, "grid")          # header flag is ignored for grid
    cols, rows, total = session.preview("Grid Layout")
    assert cols[0] == "Column 1" and rows[0][0] == "Y \\ X" and total == 10
    assert session.check("Grid Layout") == (True, "63 valid points of 63 rows")
    assert session.default_labels("Grid Layout")["xlabel"] == "X"


def test_default_labels_follow_column_titles(session):
    assert session.default_labels("Survey A") == {
        "xlabel": "X (m)", "ylabel": "Y (m)", "cbar_label": "Potential (V)", "title": ""}
    assert session.default_labels("Survey B")["xlabel"] == "x"
    chosen = ("Height (m)", "Distance (m)", "Reading (V)")
    assert session.default_labels("Survey C", chosen)["xlabel"] == "Height (m)"


def test_check_reports_dropped_rows(session):
    ok, text = session.check("Dirty Data")
    assert ok and "26 valid points of 30 rows" in text and "dropped" in text
    ok, text = session.check("Notes only")
    assert not ok


def test_empty_file_is_reported(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(DataLoadError):
        DataSession().open(str(p))
    p.write_text("a,b,c\n")
    with pytest.raises(DataLoadError):
        DataSession().open(str(p))


def test_validate(session, tmp_path):
    assert validate(session, opts(tmp_path)) is None
    assert "at least one sheet" in validate(session, opts(tmp_path, sheets=()))
    assert "output folder" in validate(session, UserOptions(sheets=["Survey A"], output_dir="")).lower()
    assert validate(DataSession(), opts(tmp_path)) == "No file selected."
    assert "three different" in validate(session, opts(tmp_path, columns=("x", "x", "z")))


def test_plot_problems(tmp_path):
    assert plot_problem(opts(tmp_path, custom_levels=True)) is not None            # nothing filled in
    assert "larger than min" in plot_problem(opts(tmp_path, custom_levels=True, level_min=1, level_max=1, level_step=1))
    assert "step must be above" in plot_problem(opts(tmp_path, custom_levels=True, level_min=0, level_max=1, level_step=0))
    assert "levels" in plot_problem(opts(tmp_path, custom_levels=True, level_min=0, level_max=1000, level_step=0.1))
    assert "X axis" in plot_problem(opts(tmp_path, xlim=(5, 1)))
    assert "colormap" in plot_problem(opts(tmp_path, cmap="nope"))
    assert plot_problem(opts(tmp_path, custom_levels=True, level_min=0, level_max=1, level_step=0.1)) is None


def test_parse_helpers():
    assert parse_float(" 1,5 ", "x") == 1.5 and parse_float("", "x", blank_ok=True) is None
    for bad in ("abc", "", "nan", "inf"):
        with pytest.raises(OptionError):
            parse_float(bad, "x")
    assert parse_int("200", "n", 10, 2000) == 200
    for bad in ("2.5", "5", "5000"):
        with pytest.raises(OptionError):
            parse_int(bad, "n", 10, 2000)


def test_folder_is_created_when_missing(tmp_path):
    target = tmp_path / "new" / "deeper"
    assert folder_problem(str(target)) is None and target.is_dir()


def test_run_uses_options(session, tmp_path):
    o = opts(tmp_path, sheets=("Survey A", "Survey B"), file_type="svg", dpi=72, prefix="map_",
             suffix="_x", title="T", xlabel="East", on_exists="number", cmap="plasma",
             reverse_cmap=True, fill_mode="filled", show_colorbar=False, interpolation="linear",
             grid_resolution=50, invert_y=True, equal_aspect=True, font_size=12, fig_w=6, fig_h=5,
             xlim=(0, 2), ylim=(0, 3))
    cfg = make_run_config(session, o)
    results = run_batch(cfg)
    assert [r.status for r in results] == ["saved", "saved"]
    assert sorted(os.listdir(tmp_path)) == ["map_Survey A_x.svg", "map_Survey B_x.svg"]
    fig = build_sheet_figure(load_sheet(cfg.path, "Survey A", cfg.load), cfg)[0].figure
    ax = fig.axes[0]
    assert len(fig.axes) == 1                               # no colorbar
    assert (ax.get_title(), ax.get_xlabel(), ax.get_ylabel()) == ("T", "East", "Y (m)")
    assert ax.get_xlim() == (0, 2) and ax.get_ylim() == (3, 0)      # inverted Y
    assert list(fig.get_size_inches()) == [6, 5]
    assert ax.title.get_fontsize() == pytest.approx(14.4)


def test_custom_levels_are_used(session, tmp_path):
    cfg = make_run_config(session, opts(tmp_path, custom_levels=True, level_min=-0.5, level_max=-0.1,
                                         level_step=0.1))
    result = build_sheet_figure(load_sheet(cfg.path, "Survey A", cfg.load), cfg)[0]
    assert list(result.filled.levels) == pytest.approx([-0.5, -0.4, -0.3, -0.2, -0.1])


def test_column_choice_by_name_and_by_position_fallback(session, tmp_path):
    # user looked at 'Survey C' and swapped X and Y; 'Survey B' has other names -> positions are used
    o = opts(tmp_path, sheets=("Survey C", "Survey B"),
             columns=("Height (m)", "Distance (m)", "Reading (V)"), column_positions=(1, 0, 2))
    results = run_batch(make_run_config(session, o))
    assert [r.status for r in results] == ["saved", "saved"]
    assert "same column positions" in results[1].info
    # a sheet that has neither the names nor enough columns is skipped, the rest carries on
    o = opts(tmp_path, sheets=("Two Columns", "Survey C"), columns=("Height (m)", "Distance (m)", "Reading (V)"),
             column_positions=(1, 0, 2), on_exists="overwrite")
    assert [r.status for r in run_batch(make_run_config(session, o))] == ["skipped", "saved"]


def test_grid_layout_run(session, tmp_path):
    results = run_batch(make_run_config(session, opts(tmp_path, sheets=("Grid Layout",), layout="grid")))
    assert results[0].status == "saved" and "63 valid points" in results[0].info


def test_skip_rows_run(session, tmp_path):
    # without skipping, the stray text rows are simply dropped as non-numeric...
    lax = run_batch(make_run_config(session, opts(tmp_path, sheets=("Padded",), on_exists="overwrite")))[0]
    assert lax.status == "saved" and "4 non-numeric rows dropped" in lax.info
    # ...with skipping, the table is read cleanly
    good = run_batch(make_run_config(session, opts(tmp_path, sheets=("Padded",), skip_top=2, skip_bottom=2, on_exists="overwrite")))[0]
    assert good.status == "saved" and "20 valid points of 20 rows" in good.info


def test_one_bad_sheet_does_not_stop_the_others(session, tmp_path):
    results = run_batch(make_run_config(session, opts(tmp_path, sheets=("Collinear", "Two Columns", "Survey A"))))
    assert [r.status for r in results] == ["error", "skipped", "saved"]


def test_existing_file_ask_callback(session, tmp_path):
    cfg = make_run_config(session, opts(tmp_path, on_exists="ask"))
    run_batch(cfg)
    asked = []
    run_batch(cfg, ask_overwrite=lambda p: (asked.append(p), "skip")[1])
    assert len(asked) == 1 and os.listdir(tmp_path) == ["Survey A.png"]
    run_batch(cfg, ask_overwrite=lambda p: "number")
    assert sorted(os.listdir(tmp_path)) == ["Survey A (1).png", "Survey A.png"]


def test_saved_settings_roundtrip_and_cleaning(tmp_path):
    saved = to_saved(opts(tmp_path, cmap="plasma", dpi=150, level_min=1.5, custom_levels=True))
    assert clean_saved(saved)["cmap"] == "plasma" and clean_saved(saved)["level_min"] == 1.5
    junk = {"file_type": "bmp", "dpi": 999, "on_exists": "??", "header": "yes", "output_dir": 5,
            "prefix": "p", "cmap": "nope", "grid_resolution": 1, "levels": True, "transparent": True}
    assert clean_saved(junk) == {"prefix": "p", "transparent": True}


def test_settings_file_roundtrip_and_corrupt(tmp_path):
    path = str(tmp_path / "s.json")
    st = SettingsStore(path)
    st.set("last_open_dir", "D")
    st.set_values(to_saved(UserOptions(sheets=[], dpi=150)))
    assert st.save()
    again = SettingsStore(path)
    assert again.get("last_open_dir") == "D" and again.values()["dpi"] == 150
    with open(path, "w") as fh:
        fh.write("{not json")
    assert SettingsStore(path).values() == {}
