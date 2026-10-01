"""Capture the output of the ORIGINAL (pre-refactor) application as a regression baseline.

This executes `original_ContourMapApp_GUI.py` (a byte-for-byte copy of the app as it
was in the initial commit) without touching its code, with only the GUI plumbing
stubbed (file dialog, message boxes, thread start, mainloop). It then records:

  expected/<name>.png      the images the original saved
  expected_arrays.npz      X/Y/Z grids and contour levels per sheet, in call order
  expected_meta.json       per-sheet outcome (saved / skipped / error), labels, titles

Needs a display for tkinter:   xvfb-run -a python tests/baseline/generate_baseline.py
Only re-run this deliberately: the whole point is that the baseline comes from the
original code, not from the refactored code.
"""
import json
import os
import shutil
import sys
import tempfile
import types

import matplotlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ORIGINAL = os.path.join(HERE, "original_ContourMapApp_GUI.py")
SAMPLE = os.path.join(REPO, "sample_data", "half_cell_sample.xlsx")


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import matplotlib.pyplot as plt

    workdir = tempfile.mkdtemp(prefix="hcp_baseline_")
    input_path = os.path.join(workdir, os.path.basename(SAMPLE))
    shutil.copy(SAMPLE, input_path)

    # --- stub only the GUI plumbing -------------------------------------------------
    tk.Tk.mainloop = lambda self, n=0: None
    filedialog.askopenfilename = lambda *a, **k: input_path
    popups = []
    messagebox.showinfo = lambda title, msg, **k: popups.append((title, msg))
    messagebox.showerror = lambda title, msg, **k: popups.append((title, msg))

    class SyncThread:                       # run the worker inline, deterministic order
        def __init__(self, target=None, **k):
            self.target = target

        def start(self):
            self.target()

    # --- record what the original draws ---------------------------------------------
    records = []                            # one entry per contourf call (= per plotted sheet)
    orig_contourf, orig_savefig = plt.contourf, plt.savefig

    def spy_contourf(X, Y, Z, *a, **k):
        cs = orig_contourf(X, Y, Z, *a, **k)
        records.append({"X": np.array(X), "Y": np.array(Y), "Z": np.array(Z),
                        "levels": np.array(cs.levels)})
        return cs

    def spy_savefig(path, *a, **k):
        fig = plt.gcf()
        ax = fig.axes[0]
        cax = fig.axes[1]
        records[-1].update({
            "file": os.path.basename(path),
            "title": ax.get_title(), "xlabel": ax.get_xlabel(), "ylabel": ax.get_ylabel(),
            "cbar_label": cax.get_ylabel(),
            "figsize": list(fig.get_size_inches()),
            "line_levels": [float(v) for v in ax.collections[-1].levels],
            "label_texts": [t.get_text() for t in ax.texts],
            "savefig_kwargs": {kk: vv for kk, vv in k.items()},
        })
        return orig_savefig(path, *a, **k)

    plt.contourf, plt.savefig = spy_contourf, spy_savefig

    # --- run the original, unmodified ------------------------------------------------
    source = open(ORIGINAL, encoding="utf-8").read()
    ns = {"__name__": "original_app"}
    code = compile(source, ORIGINAL, "exec")
    status_texts = []
    exec(code, ns)
    ns["threading"] = types.SimpleNamespace(Thread=SyncThread)
    orig_config = ns["status_label"].config
    ns["status_label"].config = lambda **k: (status_texts.append(k.get("text")), orig_config(**k))[1]
    ns["generate_contour"]()

    # --- write baseline --------------------------------------------------------------
    out_img = os.path.join(HERE, "expected")
    shutil.rmtree(out_img, ignore_errors=True)
    os.makedirs(out_img)
    arrays, meta_sheets = {}, []
    for i, rec in enumerate(records):
        for key in ("X", "Y", "Z", "levels"):
            arrays[f"{i}_{key}"] = rec[key]
        shutil.copy(os.path.join(workdir, rec["file"]), os.path.join(out_img, rec["file"]))
        meta_sheets.append({k: v for k, v in rec.items() if k not in ("X", "Y", "Z", "levels")})
    np.savez_compressed(os.path.join(HERE, "expected_arrays.npz"), **arrays)

    meta = {
        "generated_with": {"matplotlib": matplotlib.__version__, "numpy": np.__version__,
                           "python": sys.version.split()[0]},
        "input_file": os.path.basename(input_path),
        "plotted": meta_sheets,
        # outcomes for sheets that did not produce an image, as the original reported them
        "status_messages": [t for t in status_texts if t and not t.startswith("✅ Saved")],
        "final_popup": popups[-1][1] if popups else None,
    }
    with open(os.path.join(HERE, "expected_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)

    print("baseline written:", len(records), "images")
    for m in meta_sheets:
        print("  ", m["file"])
    for t in meta["status_messages"]:
        print("  ", t)
    shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
