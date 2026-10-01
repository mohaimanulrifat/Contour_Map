"""Output file naming: sanitising, prefix/suffix/custom names and overwrite handling.

Pure functions, no GUI. Half Cell Potential uses the original app's naming rule
("legacy"); Universal mode uses Windows-safe sanitising and the user's options.
"""
import os
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

ON_EXISTS_CHOICES = ("ask", "number", "overwrite")

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_BASENAME = 150


@dataclass(frozen=True)
class NamingOptions:
    pattern: str = "{sheet}"      # placeholders: {file} (data file name without extension), {sheet}
    prefix: str = ""
    suffix: str = ""
    custom_name: str = ""         # replaces the pattern, but only when ONE sheet is processed
    legacy: bool = False          # original app's rule (see sanitize_legacy); Half Cell Potential
    on_exists: str = "number"     # "ask" | "number" | "overwrite"


def sanitize_legacy(name: str) -> str:
    """The original app's rule: keep letters, digits, space, '_' and '-'; everything else -> '_'."""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in str(name))


def sanitize_windows(name: str) -> str:
    """Make `name` a legal Windows file name (without extension)."""
    s = _ILLEGAL.sub("_", str(name))
    s = s.strip().rstrip(". ")
    if s.split(".")[0].upper() in _RESERVED:
        s = "_" + s
    s = s[:MAX_BASENAME].rstrip(". ")
    return s or "map"


def build_basename(opts: NamingOptions, file_base: str, sheet: str, single_sheet: bool = False) -> str:
    """File name without extension for one sheet."""
    if opts.legacy:
        # exactly the original: '<file>_<sanitised sheet>' (the file name is not touched)
        return opts.prefix + opts.pattern.format(file=file_base, sheet=sanitize_legacy(sheet)) + opts.suffix
    if single_sheet and opts.custom_name.strip():
        core = opts.custom_name.strip()
    else:
        core = opts.pattern.format(file=file_base, sheet=sheet)
    return sanitize_windows(opts.prefix + core + opts.suffix)


def numbered(path: str, taken: Iterable[str] = ()) -> str:
    """First of 'name (1).ext', 'name (2).ext' ... that neither exists nor is in `taken`."""
    taken = {os.path.normcase(p) for p in taken}
    root, ext = os.path.splitext(path)
    n = 1
    while True:
        cand = f"{root} ({n}){ext}"
        if not os.path.exists(cand) and os.path.normcase(cand) not in taken:
            return cand
        n += 1


def resolve_path(directory: str, basename: str, ext: str, opts: NamingOptions,
                 used: set, ask: Callable[[str], str] = lambda p: "number") -> Optional[str]:
    """Final output path, or None if the user chose to skip.

    `used` holds paths already written in this batch: those are never overwritten (two sheets
    that end up with the same name get numbered), whatever `on_exists` says.
    """
    path = os.path.join(directory, f"{basename}.{ext}")
    key = os.path.normcase(path)
    if key in {os.path.normcase(p) for p in used}:
        return numbered(path, used)
    if os.path.exists(path):
        choice = opts.on_exists
        if choice == "ask":
            choice = ask(path)
        if choice == "number":
            return numbered(path, used)
        if choice == "skip":
            return None
    return path
