"""Print the GitHub release notes for a version: its CHANGELOG section plus download help.

    python tools/release_notes.py 1.0.0 > release_notes.md
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def changelog_section(version: str) -> str:
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    m = re.search(rf"^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise SystemExit(f"CHANGELOG.md has no section for version {version}")
    return m.group(1).strip()


def notes(version: str) -> str:
    return f"""**Contour Map Generator {version}**: turn X / Y / Z data from Excel, CSV and text files into contour maps. Free, for Windows.

## Which file do I download?

| File | What it is |
|---|---|
| `ContourMapGenerator-{version}-win64.zip` | **Recommended.** The app with its files folder, sample data, terms and licences. Unblock it, unzip it, double-click `ContourMapGenerator.exe`. |
| `ContourMapGenerator-{version}-portable.exe` | **One single file**, no folder. Put it anywhere and run it. It starts a little slower, because it unpacks itself each time. |
| `SHA256SUMS.txt` | Checksums, to check your download. |

Windows 10 or 11, 64-bit. Nothing to install. If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**: the app is not signed with a paid certificate yet.

## What changed

{changelog_section(version)}

## Check your download

In PowerShell, in the folder with the file:

```powershell
Get-FileHash .\\ContourMapGenerator-{version}-win64.zip -Algorithm SHA256
```

Compare it with the line for that file in `SHA256SUMS.txt`.

Free for personal and commercial use; the maps you make are yours. See [TERMS.md](https://github.com/mohaimanulrifat/Contour_Map/blob/main/TERMS.md).
"""


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.write(notes(sys.argv[1]))
