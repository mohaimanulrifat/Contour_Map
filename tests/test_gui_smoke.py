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


def pump(app, seconds=2.0, until=None):
    t0 = time.time()
    while time.time() - t0 < seconds:
        app.update()
        if until and until():
            return True
        time.sleep(0.02)
    return until() if until else None


def test_live_map_preview_follows_settings_and_reports_problems(app):
    app.open_file()
    app.ptabs.select("map")
    assert pump(app, 10, lambda: app.mapview.canvas is not None)
    assert "63 valid points" in app.mapview.info.get()
    fig = app.mapview.canvas.figure
    assert fig.axes[0].get_xlabel() == "X (m)"
    app.label_vars["xlabel"].set("Easting")                    # a setting changes -> redraw
    assert pump(app, 10, lambda: app.mapview.canvas is not None and app.mapview.canvas.figure is not fig
                and app.mapview.canvas.figure.axes[0].get_xlabel() == "Easting")
    app.res_var.set("abc")                                      # bad value -> message, no crash
    assert pump(app, 5, lambda: "Grid resolution" in app.mapview.msg.cget("text"))
    app.res_var.set("100")
    app.preview_var.set("Collinear")
    app._on_preview_sheet()
    assert pump(app, 10, lambda: "triangulated" in app.mapview.msg.cget("text"))


def test_map_preview_zoom_pan_buttons_toggle(app):
    app.open_file()
    app.ptabs.select("map")
    assert pump(app, 10, lambda: app.mapview.canvas is not None)
    app.mapview._tool("zoom")
    assert app.mapview.btn["zoom"]._active and not app.mapview.btn["pan"]._active
    app.mapview._tool("pan")
    assert app.mapview.btn["pan"]._active and not app.mapview.btn["zoom"]._active


def test_help_menu_about_and_viewers_open(app):
    from contourmap import dialogs
    labels = [app.help_menu.entrycget(i, "label") for i in range(app.help_menu.index("end") + 1)
              if app.help_menu.type(i) == "command"]
    assert labels[0].startswith("How to use") and "Check for updates" in labels and labels[-1].startswith("About")
    about = dialogs.AboutDialog(app, lambda: None, lambda: None, lambda: None)
    app.update()
    about._copy_info()
    assert "Contour Map Generator 1.0.0" in app.clipboard_get()
    about.destroy()
    for show in (app._show_how_to, app._show_terms, app._show_licences):
        before = len(app.winfo_children())
        show()
        app.update()
        assert len(app.winfo_children()) == before + 1
        app.winfo_children()[-1].destroy()


def test_update_check_reports_results_without_freezing(app, monkeypatch):
    from tkinter import messagebox
    from contourmap import updates
    seen = []
    monkeypatch.setattr(updates, "check", lambda: updates.UpdateResult("current", "1.0.0", "1.0.0"))
    monkeypatch.setattr(messagebox, "showinfo", lambda t, m, **k: seen.append(m))
    app.check_for_updates()
    assert pump(app, 5, lambda: seen)
    assert "latest version" in seen[0]
    monkeypatch.setattr(updates, "check", lambda: (_ for _ in ()).throw(updates.UpdateError("offline")))
    monkeypatch.setattr(messagebox, "askyesno", lambda t, m, **k: seen.append(m) or False)
    app.check_for_updates()
    assert pump(app, 5, lambda: len(seen) == 2)
    assert "offline" in seen[1]
