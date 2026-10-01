"""Mode presets.

A *mode* is just data: a ModePreset bundling default plot settings, how columns are
chosen, and which GUI controls are visible/locked. To add a new test type, create a
ModePreset and add it to MODES -- the GUI and engine need no changes.
"""
from dataclasses import dataclass, field, replace
from typing import Optional, Tuple


@dataclass(frozen=True)
class PlotSettings:
    """Everything the plotting engine needs. Defaults = the Half Cell Potential look."""
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
    cmap: str = "plasma"
    reverse_cmap: bool = False
    line_color: str = "k"
    line_width: float = 0.5
    show_labels: bool = True              # inline contour labels
    label_fontsize: float = 8
    label_format: str = "%.3f"
    # decorations
    show_points: bool = False
    show_grid: bool = True
    show_colorbar: bool = True
    equal_aspect: bool = False
    invert_x: bool = False
    invert_y: bool = False
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    font_size: Optional[float] = None     # None = matplotlib default
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


@dataclass(frozen=True)
class ModePreset:
    name: str
    description: str
    plot: PlotSettings
    output: OutputSettings = OutputSettings()
    # How x/y/z columns are chosen:
    #   "auto_hcp" -> legacy rule: columns named x/y/z, else the first three columns (locked)
    #   "user"     -> the user picks them in the GUI
    column_mode: str = "user"
    # Default for 'Use first row as column titles'
    header_row: bool = True
    # GUI switches
    show_column_pickers: bool = True
    show_plot_settings: bool = True
    # Behaviour of output naming: pattern with {file} and {sheet}
    default_name_pattern: str = "{sheet}"
    # Where images go by default: "input_folder" (legacy) or "remembered"
    default_output: str = "remembered"
    available: bool = True                # False = listed in the dropdown but not selectable yet


HALF_CELL = ModePreset(
    name="Half Cell Potential",
    description="ASTM C876-15 half-cell potential survey. x/y/z are found by header name "
                "(else the first three columns); the plot style is locked.",
    plot=PlotSettings(
        title="Contour Map Based on ASTM C876-15",
        cbar_label="Corrosion Potential (V)",
    ),
    output=OutputSettings(file_type="png", dpi=300, bbox_tight=True),
    column_mode="auto_hcp",
    show_column_pickers=False,
    show_plot_settings=False,
    default_name_pattern="{file}_{sheet}",
    default_output="input_folder",
)

UNIVERSAL = ModePreset(
    name="Universal (custom data)",
    description="Any X/Y/Z data: pick the columns and the plot style yourself.",
    plot=PlotSettings(
        interpolation="linear",
        levels=10,
        cmap="viridis",
        show_labels=False,
        show_points=True,
        show_grid=False,
        line_width=0.4,
        label_format="%g",
        figsize=(8, 6),
    ),
    output=OutputSettings(file_type="png", dpi=300, bbox_tight=True),
    column_mode="user",
    available=False,        # enabled in Stage 3
)

MODES = {m.name: m for m in (HALF_CELL, UNIVERSAL)}
DEFAULT_MODE = HALF_CELL.name


def with_plot(preset: ModePreset, **changes) -> ModePreset:
    """Copy of a preset with some plot settings changed."""
    return replace(preset, plot=replace(preset.plot, **changes))
