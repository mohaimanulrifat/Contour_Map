"""Drives the real window headlessly (needs a display; skipped where tkinter/Tk is unavailable)."""
import os
import shutil
import time

import pytest

tk = pytest.importorskip("tkinter")

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "sample_multisheet.xlsx")


@pytest.fixture
def app(tmp_path, monkeypatch):
    from tkinter import filedialog, messagebox
    from contourmap.gui import App
    from contourmap.settings import SettingsStore
    data = tmp_path / "sample_multisheet.xlsx"
    shutil.copy(SAMPLE, data)
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **k: str(data))
    popups = []
    for name in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(messagebox, name, lambda t, m, **k: popups.append((t, m)))
    monkeypatch.setattr(messagebox, "askyesnocancel", lambda t, m, **k: False)
    try:
        a = App(SettingsStore(str(tmp_path / "settings.json")))
    except tk.TclError:
        pytest.skip("no display available")
    a.popups = popups
    a.out = tmp_path / "out"
    yield a
    a.destroy()


def run(app, timeout=60):
    app.generate()
    t0 = time.time()
    while app.worker is not None and time.time() - t0 < timeout:
        app.update()
        time.sleep(0.02)
    app.update()


def test_open_preview_and_generate(app):
    app.open_file()
    assert [v.get() for v in app.col_vars] == ["X (m)", "Y (m)", "Potential (V)"]
    assert len(app.tree.get_children()) == 20
    assert "63 valid points" in app.col_status.get()
    assert app.label_vars["xlabel"].get() == "X (m)"
    app.out_dir_var.set(str(app.out))
    run(app)
    names = sorted(os.listdir(app.out))
    assert "Survey A.png" in names and "Collinear.png" not in names and len(names) == 6
    assert "✖ Collinear" in app.log.get("1.0", "end") and "⚠ Two Columns" in app.log.get("1.0", "end")


def test_header_toggle_and_skip_rows_refresh_preview(app):
    app.open_file()
    app.header_var.set(False)
    app._on_reading_change()
    assert app.tree.heading(app.tree["columns"][0])["text"] == "Column 1"
    app.header_var.set(True)
    app.preview_var.set("Padded")
    app.skip_top_var.set("2")
    app.skip_bottom_var.set("2")
    app._on_reading_change()
    assert app.tree.heading(app.tree["columns"][0])["text"] == "x"
    assert "20 of 20 rows" in app.preview_info.get()


def test_edited_label_applies_to_all_sheets_untouched_follow_titles(app):
    app.open_file()
    app.label_vars["title"].set("My title")
    app.preview_var.set("Survey B")
    app._refresh_preview()
    assert app.label_vars["title"].get() == "My title"        # user text kept
    assert app.label_vars["xlabel"].get() == "x"               # untouched box follows the sheet


def test_grid_layout_via_gui(app):
    app.open_file()
    app.layout_var.set("grid")
    app._on_reading_change()
    app.preview_var.set("Grid Layout")
    app._refresh_preview()
    assert "63 valid points" in app.col_status.get()
    app.all_var.set(False)
    app._on_all_toggle()
    for name, var in app.sheet_vars.items():
        var.set(name == "Grid Layout")
    app._on_sheet_toggle()
    app.out_dir_var.set(str(app.out))
    run(app)
    assert os.listdir(app.out) == ["Grid Layout.png"]


def test_bad_inputs_show_friendly_messages_and_do_not_start(app):
    app.open_file()
    app.out_dir_var.set(str(app.out))
    app.res_var.set("abc")
    app.generate()
    assert app.worker is None and "Grid resolution" in app.popups[-1][1]
    app.res_var.set("200")
    app.levmode_var.set("custom")
    app.generate()
    assert app.worker is None and "Custom levels" in app.popups[-1][1]
    app.levmode_var.set("number")
    app.lim_vars["xmin"].set("1")
    app.generate()
    assert app.worker is None and "both min and max" in app.popups[-1][1]


def test_settings_are_remembered_between_sessions(app, tmp_path):
    from contourmap.gui import App
    from contourmap.settings import SettingsStore
    app.cmap_var.set("plasma")
    app.dpi_var.set("150")
    app.type_var.set("PDF")
    app._save_settings()
    again = App(SettingsStore(str(tmp_path / "settings.json")))
    try:
        assert (again.cmap_var.get(), again.dpi_var.get(), again.type_var.get()) == ("plasma", "150", "PDF")
    finally:
        again.destroy()
