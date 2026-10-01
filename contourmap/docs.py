"""Bundled documents shown in the Help menu: how to use, terms, third-party licences."""
import os
import re

from .branding import resource_path

MISSING = "This document was not found next to the app."


def read(*parts: str) -> str:
    try:
        with open(resource_path(*parts), "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return MISSING


def plain(markdown: str) -> str:
    """Markdown -> readable plain text (headings, bold, code marks and table pipes removed)."""
    out = []
    for line in markdown.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = line.replace("**", "").replace("`", "")
        if re.fullmatch(r"\|?\s*[-:| ]+\|?\s*", line) and "-" in line:
            continue                                   # table separator row
        if line.startswith("|"):
            line = "  ".join(c.strip() for c in line.strip().strip("|").split("|"))
        out.append(line)
    return "\n".join(out).strip() + "\n"


def how_to_use() -> str:
    return read("assets", "help", "how_to_use.txt")


def terms() -> str:
    text = read("TERMS.md")
    return text if text == MISSING else plain(text)


def third_party() -> str:
    """The notices table followed by the full text of every bundled licence."""
    head = read("THIRD_PARTY_NOTICES.md")
    parts = [head if head == MISSING else plain(head)]
    folder = resource_path("licenses")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder), key=str.lower):
            if name.lower().endswith(".txt"):
                parts.append("=" * 78 + f"\n{name[:-4].replace('_', ' ')}\n" + "=" * 78 + "\n"
                             + read("licenses", name).strip())
    return "\n\n".join(parts) + "\n"
