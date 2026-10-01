import os

import pytest

from contourmap.naming import NamingOptions, build_basename, numbered, resolve_path, sanitize_windows


def test_sanitize_windows_replaces_illegal_characters():
    assert sanitize_windows('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"
    assert sanitize_windows("ok name (1)") == "ok name (1)"


@pytest.mark.parametrize("bad", ["CON", "nul", "COM1", "lpt9", "con.txt"])
def test_sanitize_windows_reserved_names(bad):
    assert sanitize_windows(bad).startswith("_")


def test_sanitize_windows_trailing_dots_spaces_and_empty():
    assert sanitize_windows("name. . ") == "name"
    assert sanitize_windows("   ") == "map"
    assert sanitize_windows("???") == "___"
    assert len(sanitize_windows("x" * 500)) <= 150


def test_basename_default_is_sheet_name():
    assert build_basename(NamingOptions(), "book", "Sheet 1") == "Sheet 1"


def test_basename_prefix_suffix_and_file_pattern():
    o = NamingOptions(pattern="{file}_{sheet}", prefix="P-", suffix="-S")
    assert build_basename(o, "book", "S1") == "P-book_S1-S"


def test_custom_name_only_for_single_sheet():
    o = NamingOptions(custom_name="my map", prefix="x_")
    assert build_basename(o, "book", "S1", single_sheet=True) == "x_my map"
    assert build_basename(o, "book", "S1", single_sheet=False) == "x_S1"


def test_resolve_path_free_name_is_unchanged(tmp_path):
    assert resolve_path(str(tmp_path), "m", "png", NamingOptions(), set()) == str(tmp_path / "m.png")


def test_numbering_and_overwrite_and_skip(tmp_path):
    (tmp_path / "m.png").write_bytes(b"x")
    d = str(tmp_path)
    assert resolve_path(d, "m", "png", NamingOptions(on_exists="number"), set()) == str(tmp_path / "m (1).png")
    assert resolve_path(d, "m", "png", NamingOptions(on_exists="overwrite"), set()) == str(tmp_path / "m.png")
    assert resolve_path(d, "m", "png", NamingOptions(on_exists="ask"), set(), ask=lambda p: "skip") is None
    assert resolve_path(d, "m", "png", NamingOptions(on_exists="ask"), set(), ask=lambda p: "number") == str(tmp_path / "m (1).png")


def test_names_clashing_inside_one_batch_are_never_overwritten(tmp_path):
    used = {str(tmp_path / "m.png")}
    got = resolve_path(str(tmp_path), "m", "png", NamingOptions(on_exists="overwrite"), used)
    assert got == str(tmp_path / "m (1).png")


def test_numbered_skips_taken(tmp_path):
    (tmp_path / "a (1).png").write_bytes(b"x")
    assert numbered(str(tmp_path / "a.png"), {str(tmp_path / "a (2).png")}) == str(tmp_path / "a (3).png")
