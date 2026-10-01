"""Generate the sample files in sample_data/ (deterministic, fixed seed).

Run from the repo root:  python tools/make_sample_data.py

sample_multisheet.xlsx covers the situations the app has to handle:
  Survey A       regular grid of points, named columns
  Survey B       scattered points, columns literally x / y / z
  Survey C       4 columns (the 4th is text), X/Y/Z not named
  Dirty Data     blank cells and text mixed into the numbers (rows get dropped)
  Padded         2 title rows above the table and 2 'total' rows below it (use skip rows)
  Grid Layout    matrix: first row = X values, first column = Y values, cells = Z
  Two Columns    only 2 columns                       -> skipped
  Notes only     3 columns of text                    -> skipped (no numeric data)
  Collinear      all points on one line               -> interpolation fails (error)

sample_scattered.csv is a plain comma-separated file with scattered terrain heights.
"""
import os

import numpy as np
import pandas as pd
from openpyxl import Workbook

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "sample_data")


def field(x, y, rng, noise=0.01):
    """Smooth synthetic field (volts) with one hotspot."""
    base = -0.20 - 0.04 * x + 0.02 * y
    hotspot = -0.22 * np.exp(-((x - 1.5) ** 2 + (y - 2.0) ** 2) / 0.8)
    return np.round(base + hotspot + rng.normal(0, noise, size=np.shape(x)), 3)


def write_excel(path, rng):
    gx, gy = np.meshgrid(np.arange(0, 3.01, 0.5), np.arange(0, 4.01, 0.5))
    survey_a = pd.DataFrame({"X (m)": gx.ravel(), "Y (m)": gy.ravel(),
                             "Potential (V)": field(gx.ravel(), gy.ravel(), rng)})

    wx, wy = np.round(rng.uniform(0, 3, 40), 2), np.round(rng.uniform(0, 4, 40), 2)
    survey_b = pd.DataFrame({"x": wx, "y": wy, "z": field(wx, wy, rng)})

    cx, cy = np.round(rng.uniform(0, 6, 30), 2), np.round(rng.uniform(0, 2, 30), 2)
    survey_c = pd.DataFrame({"Distance (m)": cx, "Height (m)": cy,
                             "Reading (V)": field(cx / 2, cy * 2, rng), "Notes": ["ok"] * 30})

    dx, dy = np.round(rng.uniform(0, 3, 30), 2), np.round(rng.uniform(0, 4, 30), 2)
    dirty = pd.DataFrame({"x": dx, "y": dy, "z": field(dx, dy, rng)}).astype(object)
    dirty.loc[3, "z"] = None
    dirty.loc[7, "z"] = "n/a"
    dirty.loc[12, "x"] = "--"
    dirty.loc[20, "y"] = None

    two = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    notes = pd.DataFrame({"a": ["foo", "bar", "baz"], "b": ["q", "r", "s"], "c": ["u", "v", "w"]})
    collinear = pd.DataFrame({"x": [0.0, 1.0, 2.0, 3.0, 4.0], "y": [0.0, 1.0, 2.0, 3.0, 4.0],
                              "z": [-0.2, -0.25, -0.3, -0.28, -0.22]})

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in [("Survey A", survey_a), ("Survey B", survey_b), ("Survey C", survey_c),
                         ("Dirty Data", dirty)]:
            df.to_excel(writer, sheet_name=name, index=False)

        # Padded: 2 title rows, the table, 2 footer rows
        pad = survey_b.head(20)
        pad.to_excel(writer, sheet_name="Padded", index=False, startrow=2)
        ws = writer.sheets["Padded"]
        ws["A1"] = "Site report - confidential"
        ws["A2"] = "Measured 2024-06-01"
        ws.cell(row=2 + len(pad) + 2, column=1, value="Total points")
        ws.cell(row=2 + len(pad) + 3, column=1, value="Checked by: ____")

        # Grid Layout: corner cell, X values across the top, Y values down the side
        xs, ys = np.arange(0, 3.01, 0.5), np.arange(0, 4.01, 0.5)
        zz = field(*np.meshgrid(xs, ys), rng)
        grid = pd.DataFrame(zz, index=ys, columns=xs)
        grid.index.name = "Y \\ X"
        grid.to_excel(writer, sheet_name="Grid Layout")

        for name, df in [("Two Columns", two), ("Notes only", notes), ("Collinear", collinear)]:
            df.to_excel(writer, sheet_name=name, index=False)


def write_csv(path, rng):
    e, n = np.round(rng.uniform(0, 100, 60), 1), np.round(rng.uniform(0, 80, 60), 1)
    h = 10 + 6 * np.exp(-((e - 40) ** 2 + (n - 30) ** 2) / 600) + 0.04 * e + rng.normal(0, 0.15, 60)
    pd.DataFrame({"Easting (m)": e, "Northing (m)": n, "Elevation (m)": np.round(h, 2)}).to_csv(path, index=False)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(20240601)
    write_excel(os.path.join(OUT_DIR, "sample_multisheet.xlsx"), rng)
    write_csv(os.path.join(OUT_DIR, "sample_scattered.csv"), rng)
    print("wrote", os.path.normpath(OUT_DIR))


if __name__ == "__main__":
    main()
