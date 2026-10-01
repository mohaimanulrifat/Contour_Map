import json
import os
import shutil

import pytest

from contourmap import presets
from contourmap.data_loader import DataLoadError
from contourmap.runner import run_batch
from contourmap.session import (DataSession, UserOptions, clean_saved, folder_problem,
                                make_run_config, to_saved, validate)
from contourmap.settings import SettingsStore

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "half_cell_sample.xlsx")
UNI, HCP = presets.UNIVERSAL, presets.HALF_CELL


@pytest.fixture
def session():
    s = DataSession()
    s.open(SAMPLE)
    return s


def test_preview_limits_rows_and_keeps_all_columns(session):
    cols, rows, total = session.preview("Column C")
    assert cols == ["Distance (m)", "Height (m)", "HCP (V)", "Notes"]
    assert len(rows) == 20 and total == 30


def test_header_toggle_renames_columns(session):
    session.set_header(False)
    cols, rows, total = session.preview("Slab A")
    assert cols == ["Column 1", "Column 2", "Column 3"]
    assert total == 64            # the old title row is now data
    session.set_header(True)
    assert session.preview("Slab A")[0][0] == "X (m)"


def test_default_labels_follow_column_titles(session):
    assert session.default_labels("Slab A", UNI) == {
        "xlabel": "X (m)", "ylabel": "Y (m)", "cbar_label": "Half-cell potential (V vs CSE)", "title": ""}
    assert session.default_labels("Wall (B)", UNI)["xlabel"] == "x"


def test_empty_file_is_reported(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(DataLoadError):
        DataSession().open(str(p))
    p.write_text("a,b,c\n")
    with pytest.raises(DataLoadError):
        DataSession().open(str(p))


def test_validate(session, tmp_path):
    ok = UserOptions(sheets=["Slab A"], output_dir=str(tmp_path))
    assert validate(UNI, session, ok) is None
    assert "at least one sheet" in validate(UNI, session, UserOptions(sheets=[], output_dir=str(tmp_path)))
    assert "output folder" in validate(UNI, session, UserOptions(sheets=["Slab A"], output_dir="")).lower()
    assert validate(UNI, DataSession(), ok) == "No file selected."
    assert validate(HCP, session, UserOptions(sheets=[], output_dir="")) is None   # locked format


def test_folder_is_created_when_missing(tmp_path):
    target = tmp_path / "new" / "deeper"
    assert folder_problem(str(target)) is None and target.is_dir()


def test_hcp_config_ignores_user_options(session, tmp_path):
    cfg = make_run_config(HCP, session, UserOptions(sheets=["Slab A"], output_dir=str(tmp_path),
                                                    file_type="pdf", dpi=72, title="x"))
    assert cfg.sheets == session.sheets and cfg.output_dir == os.path.dirname(SAMPLE)
    assert cfg.output.file_type == "png" and cfg.output.dpi == 300
    assert cfg.plot.title == "Contour Map Based on ASTM C876-15"


def test_universal_run_uses_options(session, tmp_path):
    opts = UserOptions(sheets=["Slab A", "Wall (B)"], output_dir=str(tmp_path), file_type="svg",
                       dpi=72, prefix="map_", suffix="_x", title="T", xlabel="East", on_exists="number")
    cfg = make_run_config(UNI, session, opts)
    results = run_batch(cfg)
    assert [r.status for r in results] == ["saved", "saved"]
    assert sorted(os.listdir(tmp_path)) == ["map_Slab A_x.svg", "map_Wall (B)_x.svg"]
    # user text overrides the labels; untouched ones follow the sheet's own column titles
    from contourmap.data_loader import load_sheet
    from contourmap.runner import build_sheet_figure
    fig = build_sheet_figure(load_sheet(cfg.path, "Slab A", cfg.load), cfg)[0].figure
    assert (fig.axes[0].get_title(), fig.axes[0].get_xlabel(), fig.axes[0].get_ylabel()) == ("T", "East", "Y (m)")
    assert fig.axes[1].get_ylabel() == "Half-cell potential (V vs CSE)"


def test_one_bad_sheet_does_not_stop_the_others(session, tmp_path):
    opts = UserOptions(sheets=["Collinear", "Two Columns", "Slab A"], output_dir=str(tmp_path))
    results = run_batch(make_run_config(UNI, session, opts))
    assert [r.status for r in results] == ["error", "skipped", "saved"]


def test_existing_file_ask_callback(session, tmp_path):
    opts = UserOptions(sheets=["Slab A"], output_dir=str(tmp_path), on_exists="ask")
    cfg = make_run_config(UNI, session, opts)
    run_batch(cfg)
    asked = []
    run_batch(cfg, ask_overwrite=lambda p: (asked.append(p), "skip")[1])
    assert len(asked) == 1 and os.listdir(tmp_path) == ["Slab A.png"]
    run_batch(cfg, ask_overwrite=lambda p: "number")
    assert sorted(os.listdir(tmp_path)) == ["Slab A (1).png", "Slab A.png"]


def test_clean_saved_drops_invalid_values():
    raw = {"file_type": "bmp", "dpi": 999, "on_exists": "??", "header": "yes",
           "output_dir": 5, "prefix": "p", "transparent": True}
    assert clean_saved(raw) == {"prefix": "p", "transparent": True}


def test_settings_roundtrip_and_corrupt_file(tmp_path):
    path = str(tmp_path / "s.json")
    st = SettingsStore(path)
    st.set("last_mode", "X")
    st.set_mode("Universal (custom data)", to_saved(UserOptions(sheets=[], output_dir="D", dpi=150)))
    assert st.save()
    again = SettingsStore(path)
    assert again.get("last_mode") == "X" and again.mode("Universal (custom data)")["dpi"] == 150
    with open(path, "w") as fh:
        fh.write("{not json")
    assert SettingsStore(path).mode("anything") == {}
