"""Interpolation and plotting. No GUI, no file dialogs, no pyplot (thread-safe, embeddable).

render_figure() turns scattered x/y/z points + PlotSettings into a matplotlib Figure.
save_figure() writes it to disk.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from matplotlib import colormaps
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from scipy.interpolate import griddata

from .defaults import OutputSettings, PlotSettings

INTERPOLATIONS = ("linear", "cubic", "nearest")
FILE_TYPES = ("png", "jpg", "pdf", "svg", "tiff")
FILL_MODES = ("filled", "lines", "both")


class PlotError(Exception):
    """Something the user can act on (message is shown in a dialog / the log)."""


@dataclass
class GridResult:
    X: np.ndarray
    Y: np.ndarray
    Z: np.ndarray
    method_used: str
    notes: List[str] = field(default_factory=list)


@dataclass
class RenderResult:
    figure: Figure
    grid: GridResult
    filled: object = None      # matplotlib ContourSet of the filled contours (or None)
    lines: object = None       # ContourSet of the contour lines (or None)


# ----------------------------------------------------------------------------- interpolation
def interpolate(x, y, z, method: str = "cubic", resolution: int = 200,
                mask_outside_hull: bool = False) -> GridResult:
    """Interpolate scattered points onto a regular `resolution` x `resolution` grid.

    'cubic' falls back to 'linear' when cubic fails or returns nothing (small / awkward
    data sets); the fallback is reported in GridResult.notes.
    """
    x, y, z = (np.asarray(a, dtype=float) for a in (x, y, z))
    if method not in INTERPOLATIONS:
        raise PlotError(f"Unknown interpolation method '{method}'.")
    if resolution < 2:
        raise PlotError("Grid resolution must be at least 2.")
    n_min = 1 if method == "nearest" else 3
    if len(x) < n_min:
        raise PlotError(f"Too few points to interpolate: {len(x)} valid point(s), "
                        f"at least {n_min} needed for '{method}'.")
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        raise PlotError("All points share the same X (or the same Y) value, so there is no "
                        "2-D area to map. Check that the X and Y columns are right.")

    xi = np.linspace(np.min(x), np.max(x), resolution)
    yi = np.linspace(np.min(y), np.max(y), resolution)
    X, Y = np.meshgrid(xi, yi)
    notes: List[str] = []
    used = method
    try:
        if method == "cubic":
            try:
                Z = griddata((x, y), z, (X, Y), method="cubic")
                if np.isnan(Z).all():
                    Z = griddata((x, y), z, (X, Y), method="linear")
                    used = "linear"
            except Exception:
                Z = griddata((x, y), z, (X, Y), method="linear")
                used = "linear"
            if used == "linear":
                notes.append("cubic interpolation was not possible for this data; used linear")
        else:
            Z = griddata((x, y), z, (X, Y), method=method)
    except Exception as e:                      # Qhull errors etc.
        text = str(e)
        if "Qhull" in text or "QH" in text:
            raise PlotError("The points cannot be triangulated (they are collinear or "
                            "duplicated). At least 3 points that do not lie on one line are "
                            "needed.") from e
        raise PlotError(f"Interpolation failed: {text}") from e

    if mask_outside_hull:
        from scipy.spatial import Delaunay
        try:
            tri = Delaunay(np.column_stack([x, y]))
            inside = tri.find_simplex(np.column_stack([X.ravel(), Y.ravel()])) >= 0
            Z = np.where(inside.reshape(X.shape), Z, np.nan)
        except Exception as e:
            notes.append(f"could not mask outside the data hull ({e})")
    return GridResult(X, Y, Z, used, notes)


# ----------------------------------------------------------------------------- plotting
def _levels(s: PlotSettings):
    if s.level_min is not None and s.level_max is not None and s.level_step:
        if s.level_max <= s.level_min or s.level_step <= 0:
            raise PlotError("Custom levels: max must be larger than min and step above 0.")
        n = int(np.floor((s.level_max - s.level_min) / s.level_step + 1e-9)) + 1
        if n > 500:
            raise PlotError(f"Custom levels would create {n} levels; use a larger step.")
        return list(s.level_min + s.level_step * np.arange(n))
    return s.levels


def _cmap(s: PlotSettings):
    if not s.reverse_cmap:
        return s.cmap                      # pass the name straight to matplotlib
    try:
        return colormaps[s.cmap].reversed()
    except KeyError:
        raise PlotError(f"Unknown colormap '{s.cmap}'.")


def render_figure(x, y, z, settings: PlotSettings) -> RenderResult:
    """Interpolate and draw. Raises PlotError with a friendly message on failure."""
    s = settings
    if s.fill_mode not in FILL_MODES:
        raise PlotError(f"Unknown fill mode '{s.fill_mode}'.")
    grid = interpolate(x, y, z, s.interpolation, s.grid_resolution, s.mask_outside_hull)
    X, Y, Z = grid.X, grid.Y, grid.Z
    if np.isnan(Z).all():
        raise PlotError("Interpolation produced no values (all points outside the grid).")

    fig = Figure(figsize=s.figsize)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    levels = _levels(s)
    cmap = _cmap(s)

    # Draw order: filled -> colorbar -> lines -> labels.
    cb = lines = filled = None
    try:
        if s.fill_mode in ("filled", "both"):
            filled = ax.contourf(X, Y, Z, levels=levels, cmap=cmap)
            if s.show_colorbar:
                cb = fig.colorbar(filled, ax=ax, label=s.cbar_label)
        if s.fill_mode == "both":
            lines = ax.contour(X, Y, Z, levels=levels, colors=s.line_color, linewidths=s.line_width)
        elif s.fill_mode == "lines":
            lines = ax.contour(X, Y, Z, levels=levels, cmap=cmap, linewidths=max(s.line_width, 0.8))
            if s.show_colorbar:
                cb = fig.colorbar(lines, ax=ax, label=s.cbar_label)
    except ValueError as e:
        raise PlotError(f"Could not draw contours: {e}") from e

    if lines is not None and s.show_labels:
        ax.clabel(lines, inline=True, fontsize=s.label_fontsize, fmt=s.label_format)
    if s.show_points:
        ax.scatter(x, y, s=8, c="k", edgecolors="w", linewidths=0.4, zorder=5)

    ax.set_title(s.title)
    ax.set_xlabel(f"{s.xlabel or ''}")
    ax.set_ylabel(f"{s.ylabel or ''}")
    if s.show_grid:
        ax.grid(True)
    if s.xlim:
        ax.set_xlim(*s.xlim)
    if s.ylim:
        ax.set_ylim(*s.ylim)
    if s.invert_x:
        ax.invert_xaxis()
    if s.invert_y:
        ax.invert_yaxis()
    if s.equal_aspect:
        ax.set_aspect("equal", adjustable="box")

    if s.font_size:
        fs = s.font_size
        ax.title.set_fontsize(fs * 1.2)
        ax.xaxis.label.set_fontsize(fs)
        ax.yaxis.label.set_fontsize(fs)
        ax.tick_params(labelsize=fs)
        if cb is not None:
            cb.ax.yaxis.label.set_fontsize(fs)
            cb.ax.tick_params(labelsize=fs)
    return RenderResult(fig, grid, filled, lines)


# ----------------------------------------------------------------------------- saving
def save_figure(fig: Figure, path: str, out: OutputSettings) -> None:
    kwargs = {"dpi": out.dpi}
    if out.bbox_tight:
        kwargs["bbox_inches"] = "tight"
    if out.transparent and out.file_type in ("png", "svg", "pdf", "tiff"):
        kwargs["transparent"] = True
    try:
        fig.savefig(path, **kwargs)
    except PermissionError as e:
        raise PlotError(f"Cannot write '{path}' (is it open in another program?)") from e
    except OSError as e:
        raise PlotError(f"Cannot write '{path}': {e}") from e
