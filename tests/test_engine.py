import numpy as np
import pytest

from contourmap.defaults import OutputSettings, PlotSettings
from contourmap.engine import PlotError, interpolate, render_figure, save_figure


def surface(n=40, seed=1):
    rng = np.random.default_rng(seed)
    x, y = rng.uniform(0, 10, n), rng.uniform(0, 5, n)
    return x, y, 2 * x + 3 * y                    # a plane: every method must reproduce it


@pytest.mark.parametrize("method", ["linear", "cubic"])
def test_plane_is_reproduced_inside_the_hull(method):
    x, y, z = surface()
    g = interpolate(x, y, z, method, 30)
    assert g.Z.shape == (30, 30) and g.method_used == method
    ok = ~np.isnan(g.Z)
    assert ok.sum() > 300
    np.testing.assert_allclose(g.Z[ok], (2 * g.X + 3 * g.Y)[ok], atol=1e-6)


def test_nearest_fills_the_whole_grid_and_hull_mask_blanks_outside():
    x, y, z = surface()
    assert not np.isnan(interpolate(x, y, z, "nearest", 30).Z).any()
    masked = interpolate(x, y, z, "nearest", 30, mask_outside_hull=True).Z
    assert np.isnan(masked).any() and (~np.isnan(masked)).any()


def test_grid_spans_data_range_and_resolution():
    x, y, z = surface()
    g = interpolate(x, y, z, "linear", 17)
    assert g.X.shape == (17, 17)
    assert g.X.min() == pytest.approx(x.min()) and g.Y.max() == pytest.approx(y.max())


def test_cubic_falls_back_to_linear(monkeypatch):
    import contourmap.engine as eng
    real = eng.griddata

    def flaky(points, values, xi, method="linear"):
        if method == "cubic":
            raise RuntimeError("boom")
        return real(points, values, xi, method=method)
    monkeypatch.setattr(eng, "griddata", flaky)
    g = interpolate(*surface(), "cubic", 20)
    assert g.method_used == "linear" and any("cubic" in n for n in g.notes)


def test_too_few_points_and_degenerate_input_give_friendly_errors():
    with pytest.raises(PlotError, match="Too few points"):
        interpolate([0, 1], [0, 1], [1, 2], "linear", 20)
    with pytest.raises(PlotError, match="collinear"):
        interpolate([0, 1, 2, 3], [0, 1, 2, 3], [1, 2, 3, 4], "linear", 20)
    with pytest.raises(PlotError, match="same X"):
        interpolate([1, 1, 1], [0, 1, 2], [1, 2, 3], "linear", 20)
    with pytest.raises(PlotError):
        interpolate(*surface(), "spline", 20)
    with pytest.raises(PlotError):
        interpolate(*surface(), "linear", 1)


@pytest.mark.parametrize("mode,has_cbar", [("filled", True), ("lines", True), ("both", True)])
def test_fill_modes(mode, has_cbar):
    r = render_figure(*surface(), PlotSettings(fill_mode=mode, grid_resolution=40))
    assert (r.filled is not None) == (mode != "lines") and (r.lines is not None) == (mode != "filled")
    assert len(r.figure.axes) == (2 if has_cbar else 1)


def test_toggles_change_the_figure():
    base = dict(grid_resolution=40)
    on = render_figure(*surface(), PlotSettings(**base, show_labels=True, show_points=True, show_grid=True)).figure.axes[0]
    off = render_figure(*surface(), PlotSettings(**base, show_labels=False, show_grid=False,
                                                 show_colorbar=False)).figure
    assert len(on.texts) > 0 and len(on.collections) >= 3
    assert len(off.axes[0].texts) == 0 and len(off.axes) == 1
    assert not off.axes[0].xaxis.get_gridlines()[0].get_visible()


def test_reverse_colormap_and_levels():
    r = render_figure(*surface(), PlotSettings(grid_resolution=40, cmap="viridis", reverse_cmap=True,
                                               level_min=0, level_max=40, level_step=10))
    assert r.filled.get_cmap().name == "viridis_r"
    assert list(r.filled.levels) == [0, 10, 20, 30, 40]
    with pytest.raises(PlotError):
        render_figure(*surface(), PlotSettings(cmap="nope", reverse_cmap=True))
    with pytest.raises(PlotError):
        render_figure(*surface(), PlotSettings(level_min=5, level_max=1, level_step=1))


@pytest.mark.parametrize("ext", ["png", "jpg", "pdf", "svg", "tiff"])
def test_all_file_types_are_written(tmp_path, ext):
    fig = render_figure(*surface(), PlotSettings(grid_resolution=30)).figure
    path = tmp_path / f"m.{ext}"
    save_figure(fig, str(path), OutputSettings(file_type=ext, dpi=72, transparent=ext != "jpg"))
    assert path.stat().st_size > 500


def test_dpi_controls_pixel_size(tmp_path):
    from PIL import Image
    fig = render_figure(*surface(), PlotSettings(grid_resolution=30, figsize=(4, 3))).figure
    save_figure(fig, str(tmp_path / "a.png"), OutputSettings(dpi=100, bbox_tight=False))
    assert Image.open(tmp_path / "a.png").size == (400, 300)


def test_unwritable_target_is_a_friendly_error(tmp_path):
    fig = render_figure(*surface(), PlotSettings(grid_resolution=30)).figure
    with pytest.raises(PlotError, match="Cannot write"):
        save_figure(fig, str(tmp_path / "no" / "such" / "dir" / "m.png"), OutputSettings())
