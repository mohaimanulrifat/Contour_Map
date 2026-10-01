import os

from contourmap import branding, docs, version


def test_version_is_semver_and_info_has_no_personal_data():
    assert all(p.isdigit() for p in version.VERSION.split("."))
    text = version.version_info_text(branding.APP_NAME)
    assert text.startswith(f"{branding.APP_NAME} {version.VERSION}")
    for part in ("Python", "matplotlib", "SciPy", "pandas", "NumPy"):
        assert part in text
    assert os.path.expanduser("~") not in text


def test_branding_links_and_names():
    assert branding.APP_NAME == "Contour Map Generator"
    assert branding.LINKEDIN_URL.startswith("https://www.linkedin.com/in/")
    assert "@" in branding.EMAIL and branding.REPO in branding.RELEASES_URL
    assert branding.SUGGESTION_URL.endswith("suggestion.yml") and branding.PROBLEM_URL.endswith("bug_report.yml")
    assert branding.logo_path() and os.path.isfile(branding.resource_path("assets", branding.ICON_FILE))


def test_bundled_documents_exist_and_read_well():
    assert "How to make maps" in docs.how_to_use()
    terms = docs.terms()
    assert "Free to use" in terms and "#" not in terms and "**" not in terms
    tp = docs.third_party()
    assert "matplotlib" in tp and docs.MISSING not in tp and "|" not in tp.split("====")[0]


def test_plain_markdown_conversion():
    md = "# Title\n\n**bold** and `code`\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    out = docs.plain(md)
    assert "Title" in out and "bold and code" in out and "A  B" in out and "---" not in out and "1  2" in out


def test_missing_document_is_friendly(monkeypatch):
    monkeypatch.setattr(docs, "resource_path", lambda *p: os.path.join("/nonexistent", *p))
    assert docs.how_to_use() == docs.MISSING and docs.terms() == docs.MISSING


def test_every_colormap_in_the_dropdown_exists():
    import matplotlib
    from contourmap.defaults import COLORMAPS
    assert all(c in matplotlib.colormaps for c in COLORMAPS)
