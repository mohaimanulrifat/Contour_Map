import pandas as pd
import pytest

from contourmap.data_loader import (DataLoadError, LoadOptions, SheetSkipped, detect_delimiter,
                                    detect_encoding, extract_xyz, grid_to_xyz, guess_xyz,
                                    list_sheets, load_all, load_sheet, numeric_columns)


def write(tmp_path, name, text, encoding="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(encoding))
    return str(p)


@pytest.mark.parametrize("delim", [",", ";", "\t", "|"])
def test_delimiter_autodetect(tmp_path, delim):
    p = write(tmp_path, "d.csv", "\n".join(delim.join(r) for r in [["x", "y", "z"], ["1", "2", "3"], ["4", "5", "6"]]))
    df = load_sheet(p, "Sheet1")
    assert list(df.columns) == ["x", "y", "z"] and df.shape == (2, 3)


def test_whitespace_separated_txt(tmp_path):
    p = write(tmp_path, "d.txt", "x y z\n1 2 3\n4 5 6\n")
    assert load_sheet(p, "Sheet1").shape == (2, 3)


def test_utf8_bom_and_cp1252_encodings(tmp_path):
    bom = write(tmp_path, "bom.csv", "﻿x,y,z\n1,2,3\n")
    assert detect_encoding(bom) == "utf-8-sig" and list(load_sheet(bom, "Sheet1").columns) == ["x", "y", "z"]
    legacy = write(tmp_path, "l.csv", "Länge (m),y,z\n1,2,3\n", encoding="cp1252")
    assert detect_encoding(legacy) == "cp1252" and load_sheet(legacy, "Sheet1").columns[0] == "Länge (m)"


def test_plain_csv_equals_pandas_read_csv(tmp_path):
    p = write(tmp_path, "p.csv", "x,y,z\n1,2,3\n4,5,6\n")
    pd.testing.assert_frame_equal(load_sheet(p, "Sheet1"), pd.read_csv(p))


def test_header_flag_skip_rows(tmp_path):
    p = write(tmp_path, "s.csv", "title row\nx,y,z\n1,2,3\n4,5,6\ntotal,,\n")
    df = load_sheet(p, "Sheet1", LoadOptions(skip_top=1, skip_bottom=1))
    assert list(df.columns) == ["x", "y", "z"] and len(df) == 2
    raw = load_sheet(p, "Sheet1", LoadOptions(header=False))
    assert list(raw.columns) == ["Column 1", "Column 2", "Column 3"] and len(raw) == 5


def test_skip_bottom_more_than_rows_gives_empty(tmp_path):
    p = write(tmp_path, "s.csv", "x,y,z\n1,2,3\n")
    assert load_sheet(p, "Sheet1", LoadOptions(skip_bottom=5)).empty


def test_unsupported_and_missing_files(tmp_path):
    with pytest.raises(DataLoadError):
        list_sheets(str(tmp_path / "a.docx"))
    with pytest.raises(DataLoadError):
        list_sheets(str(tmp_path / "missing.xlsx"))


def test_excel_sheets(tmp_path):
    p = str(tmp_path / "b.xlsx")
    with pd.ExcelWriter(p) as w:
        pd.DataFrame({"x": [1, 2], "y": [3, 4], "z": [5, 6]}).to_excel(w, sheet_name="A", index=False)
        pd.DataFrame({"a": [1]}).to_excel(w, sheet_name="B", index=False)
    assert list_sheets(p) == ["A", "B"]
    assert set(load_all(p)) == {"A", "B"}


def test_numeric_columns_and_guess():
    df = pd.DataFrame({"name": ["a", "b", "c"], "East": [1, 2, 3], "North": [4, 5, 6], "Value": [7.0, 8.0, 9.0]})
    assert numeric_columns(df) == ["East", "North", "Value"]
    assert guess_xyz(df) == ("East", "North", "Value")
    named = pd.DataFrame({"z": [1, 2], "id": [1, 2], "x": [1, 2], "y": [3, 4]})
    assert guess_xyz(named) == ("x", "y", "z")
    assert guess_xyz(pd.DataFrame({"a": [1], "b": [2]})) == ("a", "b", None)


def test_extract_counts_empty_and_nonnumeric_rows():
    df = pd.DataFrame({"x": [1, 2, "abc", 4, None], "y": [1, 2, 3, 4, 5], "z": [1.0, None, 3.0, 4.0, 5.0]})
    d = extract_xyz(df, "x", "y", "z")
    assert len(d.x) == 2 and d.n_rows == 5 and d.n_nonnumeric == 1 and d.n_empty == 2
    assert "3 rows" not in d.summary() and "dropped" in d.summary()
    assert extract_xyz(df.head(2).assign(z=[1, 2]), "x", "y", "z").n_dropped == 0


def test_grid_to_xyz_layout():
    raw = pd.DataFrame([["corner", 10, 20, 30], [1, 1.1, 1.2, 1.3], [2, 2.1, None, 2.3]])
    long = grid_to_xyz(raw)
    assert list(long.columns) == ["X", "Y", "Z"] and len(long) == 6
    first, last = long.iloc[0], long.iloc[-1]
    assert (first.X, first.Y, first.Z) == (10, 1, 1.1) and (last.X, last.Y, last.Z) == (30, 2, 2.3)
    d = extract_xyz(long, "X", "Y", "Z")
    assert len(d.x) == 5 and d.n_empty == 1
    with pytest.raises(SheetSkipped):
        grid_to_xyz(pd.DataFrame([[1, 2]]))


def test_title_line_shorter_than_table_does_not_break_reading(tmp_path):
    p = write(tmp_path, "t.csv", "Site report\n\nx,y,z\n1,2,3\n4,5,6\n")
    raw = load_sheet(p, "Sheet1", LoadOptions(header=False))
    assert raw.shape == (4, 3)                                  # padded, nothing lost
    skipped = load_sheet(p, "Sheet1", LoadOptions(skip_top=2))
    assert list(skipped.columns) == ["x", "y", "z"] and len(skipped) == 2
    promoted = load_sheet(p, "Sheet1", LoadOptions())           # header=True on the ragged file
    assert promoted.shape[1] == 3


def test_delimiter_inside_quotes_and_decimal_commas(tmp_path):
    p = write(tmp_path, "q.csv", 'name;x;y;z\n"a;b";1,5;2;3\n"c;d";2,5;3;4\n')
    assert detect_delimiter(p, "utf-8") == ";"


def test_semicolon_files_with_decimal_commas(tmp_path):
    p = write(tmp_path, "eu.csv", "x;y;z\n1,5;2,5;3,25\n2,5;3,5;4,75\n")
    df = load_sheet(p, "Sheet1")
    assert df["x"].tolist() == [1.5, 2.5] and df["z"].tolist() == [3.25, 4.75]
