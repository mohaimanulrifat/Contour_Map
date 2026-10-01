"""`ContourMapGenerator --selftest [result.txt]`: checks that a built copy is complete.

Used by the release build to prove the packaged exe can find its files, import its parts, draw
and save a map, and open a window. Exit code 0 = all good. Results are also written to the file.
"""
import os
import sys
import tempfile
import traceback


def run(result_path=None) -> int:
    lines, failed = [], False

    def check(label, fn):
        nonlocal failed
        try:
            detail = fn()
            lines.append(f"ok    {label}" + (f": {detail}" if detail else ""))
        except Exception as e:
            failed = True
            lines.append(f"FAIL  {label}: {type(e).__name__}: {e}")
            lines.append(traceback.format_exc())

    from . import branding, docs, version

    def exists(*parts):
        p = branding.resource_path(*parts)
        assert os.path.exists(p), f"missing {p}"
        return ""

    check("version", lambda: version.VERSION)
    for rel in (("assets", branding.LOGO_FILE), ("assets", branding.ICON_FILE),
                ("assets", "fonts", "Inter-Regular.otf"), ("assets", "help", "how_to_use.txt"),
                ("TERMS.md",), ("THIRD_PARTY_NOTICES.md",), ("licenses",)):
        check("resource " + "/".join(rel), lambda r=rel: exists(*r))
    check("licence texts", lambda: str(len(docs.third_party())) + " characters" if docs.MISSING not in docs.third_party() else 1 / 0)

    def draw():
        import numpy as np
        from .defaults import DEFAULT_OUTPUT, DEFAULT_PLOT
        from .engine import render_figure, save_figure
        rng = np.random.default_rng(1)
        x, y = rng.uniform(0, 10, 40), rng.uniform(0, 5, 40)
        fig = render_figure(x, y, np.sin(x) + y, DEFAULT_PLOT).figure
        out = os.path.join(tempfile.mkdtemp(), "selftest.png")
        for ext in ("png", "pdf", "svg", "jpg", "tiff"):
            save_figure(fig, out.replace(".png", "." + ext), DEFAULT_OUTPUT.__class__(file_type=ext, dpi=72))
        return f"{os.path.getsize(out)} bytes"
    check("draw and save a map (png, pdf, svg, jpg, tiff)", draw)

    def read_files():
        import pandas as pd
        d = tempfile.mkdtemp()
        xlsx = os.path.join(d, "t.xlsx")
        pd.DataFrame({"x": [1, 2, 3], "y": [1, 2, 3], "z": [1, 2, 3]}).to_excel(xlsx, index=False)
        from .data_loader import load_sheet, list_sheets
        assert len(load_sheet(xlsx, list_sheets(xlsx)[0])) == 3
        csv = os.path.join(d, "t.csv")
        open(csv, "w").write("a;b;c\n1,5;2;3\n")
        assert load_sheet(csv, "Sheet1")["a"][0] == 1.5
        return "xlsx and csv"
    check("read Excel and CSV", read_files)

    def window():
        import tkinter as tk
        from .gui import App
        from .settings import SettingsStore
        app = App(SettingsStore(os.path.join(tempfile.mkdtemp(), "s.json")))
        app.update()
        title = app.title()
        app.destroy()
        return title
    check("open the main window", window)

    lines.append("RESULT: " + ("FAILED" if failed else "ALL OK"))
    text = "\n".join(lines) + "\n"
    if result_path:
        with open(result_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 1 if failed else 0
