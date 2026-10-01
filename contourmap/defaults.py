"""Plot / output settings (plain dataclasses) and the application defaults."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class PlotSettings:
    """Everything the plotting engine needs."""
    # interpolation
    interpolation: str = "cubic"          # "linear" | "cubic" | "nearest" (cubic falls back to linear)
    grid_resolution: int = 200            # grid points per axis
    mask_outside_hull: bool = False       # blank the area outside the convex hull of the data
    # contour drawing
    fill_mode: str = "both"               # "filled" | "lines" | "both"
    levels: int = 15                      # number of levels ...
    level_min: Optional[float] = None     # ... or custom min/max/step (all three needed)
    level_max: Optional[float] = None
    level_step: Optional[float] = None
    cmap: str = "viridis"
    reverse_cmap: bool = False
    line_color: str = "k"
    line_width: float = 0.5
    show_labels: bool = True              # inline contour labels
    label_fontsize: float = 8
    label_format: str = "%g"
    # decorations
    show_points: bool = False
    show_grid: bool = True
    show_colorbar: bool = True
    equal_aspect: bool = False
    invert_x: bool = False
    invert_y: bool = False
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    font_size: Optional[float] = None     # None = matplotlib default (10)
    figsize: Tuple[float, float] = (8, 7)
    # text (None = take from the column title / leave empty)
    title: str = ""
    xlabel: Optional[str] = None          # None = use the X column title
    ylabel: Optional[str] = None          # None = use the Y column title
    cbar_label: Optional[str] = None      # None = use the Z column title


@dataclass(frozen=True)
class OutputSettings:
    """How figures are written to disk."""
    file_type: str = "png"                # png | jpg | pdf | svg | tiff
    dpi: int = 300
    transparent: bool = False
    bbox_tight: bool = True


DEFAULT_PLOT = PlotSettings()
DEFAULT_OUTPUT = OutputSettings()

# A short, curated colormap list for the dropdown (all are built into matplotlib).
COLORMAPS = (
    "viridis", "plasma", "inferno", "magma", "cividis", "turbo",
    "jet", "rainbow", "nipy_spectral", "gist_rainbow",
    "coolwarm", "bwr", "seismic", "RdBu", "RdYlBu", "RdYlGn", "Spectral",
    "terrain", "gist_earth", "ocean",
    "Blues", "Greens", "Oranges", "Reds", "Purples", "Greys",
    "YlOrRd", "YlGnBu", "hot", "afmhot", "bone", "copper", "cubehelix",
)
INTERPOLATION_CHOICES = ("linear", "cubic", "nearest")
FILL_CHOICES = ("filled", "lines", "both")
