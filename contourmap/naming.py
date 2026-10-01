"""Output file naming. (Extended in Stage 2 with prefix/suffix/custom name/auto-numbering.)"""


def sanitize_legacy(name: str) -> str:
    """The original app's rule: keep letters, digits, space, '_' and '-'; everything else -> '_'.

    Used by Half Cell Potential mode so existing file names stay exactly the same.
    """
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in str(name))


def legacy_filename(base_name: str, sheet: str, ext: str = "png") -> str:
    """'<workbook>_<sheet>.png' -- the original app's naming."""
    return f"{base_name}_{sanitize_legacy(sheet)}.{ext}"
