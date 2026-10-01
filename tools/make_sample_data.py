"""Generate the sample Excel workbook used by the demo and the regression tests.

Deterministic (fixed seed). Run from the repo root:  python tools/make_sample_data.py

Sheets cover the situations the Half Cell Potential workflow has to handle:
  Slab A         regular grid, headers do not name z  -> first-three-columns fallback
  Wall (B)       scattered points, headers literally x / y / z; '(' ')' in the name
  Column C       4 columns, x/y/z not named           -> first three columns used
  Dirty Data     blank cells and text mixed into the numbers (rows get dropped)
  Two Columns    only 2 columns                       -> skipped
  Notes only     3 columns of text                    -> skipped (no numeric data)
  Collinear      all points on one line               -> interpolation fails (error)
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "sample_data", "half_cell_sample.xlsx")


def field(x, y, rng, noise=0.01):
    """Smooth synthetic half-cell potential field (volts) with one corrosion hotspot."""
    base = -0.20 - 0.04 * x + 0.02 * y
    hotspot = -0.22 * np.exp(-((x - 1.5) ** 2 + (y - 2.0) ** 2) / 0.8)
    return np.round(base + hotspot + rng.normal(0, noise, size=np.shape(x)), 3)


def main():
    rng = np.random.default_rng(20240601)

    gx, gy = np.meshgrid(np.arange(0, 3.01, 0.5), np.arange(0, 4.01, 0.5))
    slab = pd.DataFrame({
        "X (m)": gx.ravel(),
        "Y (m)": gy.ravel(),
        "Half-cell potential (V vs CSE)": field(gx.ravel(), gy.ravel(), rng),
    })

    wx = np.round(rng.uniform(0, 3, 40), 2)
    wy = np.round(rng.uniform(0, 4, 40), 2)
    wall = pd.DataFrame({"x": wx, "y": wy, "z": field(wx, wy, rng)})

    cx = np.round(rng.uniform(0, 6, 30), 2)
    cy = np.round(rng.uniform(0, 2, 30), 2)
    column = pd.DataFrame({
        "Distance (m)": cx,
        "Height (m)": cy,
        "HCP (V)": field(cx / 2, cy * 2, rng),
        "Notes": ["ok"] * 30,
    })

    dx = np.round(rng.uniform(0, 3, 30), 2)
    dy = np.round(rng.uniform(0, 4, 30), 2)
    dirty = pd.DataFrame({"x": dx, "y": dy, "z": field(dx, dy, rng)}).astype(object)
    dirty.loc[3, "z"] = None
    dirty.loc[7, "z"] = "n/a"
    dirty.loc[12, "x"] = "--"
    dirty.loc[20, "y"] = None

    two = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    notes = pd.DataFrame({"a": ["foo", "bar", "baz"], "b": ["q", "r", "s"], "c": ["u", "v", "w"]})
    collinear = pd.DataFrame({
        "x": [0.0, 1.0, 2.0, 3.0, 4.0],
        "y": [0.0, 1.0, 2.0, 3.0, 4.0],
        "z": [-0.2, -0.25, -0.3, -0.28, -0.22],
    })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        for name, df in [("Slab A", slab), ("Wall (B)", wall), ("Column C", column),
                         ("Dirty Data", dirty), ("Two Columns", two),
                         ("Notes only", notes), ("Collinear", collinear)]:
            df.to_excel(writer, sheet_name=name, index=False)
    print("wrote", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
