"""Generate THIRD_PARTY_NOTICES.md and licenses/*.txt from the packages installed right now.

Run from the repo root, in the same environment the release is built from:
    python tools/make_licenses.py

It follows the dependencies of the packages the app imports, copies each package's own licence
files, and adds the parts that are not Python packages (Python, Tcl/Tk, the Microsoft C++
runtime, the Inter and DejaVu fonts, the PyInstaller bootloader).
"""
import os
import re
import shutil
import sys
from importlib import metadata

from packaging.requirements import InvalidRequirement, Requirement

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "licenses")
NOTICES = os.path.join(ROOT, "THIRD_PARTY_NOTICES.md")

# what the app imports directly; everything they need is found automatically
TOP_LEVEL = ["pandas", "numpy", "scipy", "matplotlib", "openpyxl", "xlrd", "Pillow"]
LICENSE_FILE = re.compile(r"(licen[cs]e|copying|notice|authors)", re.I)
TEXT_EXT = ("", ".txt", ".md", ".rst")

# parts that are not (or not only) pip packages
EXTRA = [
    ("Python", sys.version.split()[0], "PSF-2.0 (and the licences it lists)", "https://www.python.org/"),
    ("Tcl/Tk", "8.6", "TCL (BSD-style)", "https://www.tcl.tk/"),
    ("Microsoft Visual C++ runtime", "14", "Microsoft redistributable",
     "https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist"),
    ("Inter typeface", "4.0", "SIL OFL-1.1", "https://rsms.me/inter/"),
    ("DejaVu fonts (inside matplotlib)", "2.37", "Bitstream Vera licence (free)", "https://dejavu-fonts.github.io/"),
]
NOTES = {
    "Python": "Includes the standard library, OpenSSL, libffi, zlib, bzip2, xz, expat and mpdecimal.",
    "Microsoft Visual C++ runtime": "Not open source. Shipped as Python from python.org ships it.",
    "Pillow": "Pillow's own image libraries (libjpeg-turbo, libpng, zlib and others) are listed in its file.",
    "PyInstaller (bootloader)": "GPL-2.0-or-later with the bootloader exception, which allows the bootloader to be "
                                "shipped inside other programs.",
    "SciPy": "Includes several numerical libraries; each one's licence is listed in SciPy's file.",
    "NumPy": "Includes OpenBLAS and other libraries; each one's licence is listed in NumPy's file.",
}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def dependencies(roots):
    seen, order, todo = {}, [], list(roots)
    while todo:
        name = todo.pop(0)
        key = norm(name)
        if key in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        seen[key] = dist
        order.append(key)
        for line in dist.requires or []:
            try:
                req = Requirement(line)
            except InvalidRequirement:
                continue
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
            todo.append(req.name)
    return [seen[k] for k in order]


def licence_name(meta) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) < 80 and "\n" not in lic:
        return lic
    classes = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    classes = [c for c in classes if c.lower() not in ("osi approved",)]
    return " / ".join(classes) if classes else "see the licence file"


def home_page(meta) -> str:
    if meta.get("Home-page"):
        return meta["Home-page"]
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("homepage", "home", "source", "repository", "source code"):
            return url.strip()
    return ""


def licence_texts(dist):
    texts = []
    for f in dist.files or []:
        s = str(f).replace("\\", "/")
        if ".dist-info/" not in s and ".egg-info/" not in s:
            continue
        base = os.path.basename(s)
        if LICENSE_FILE.search(base) and os.path.splitext(base)[1].lower() in TEXT_EXT:
            try:
                texts.append((base, dist.locate_file(f).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return texts


def write_license_file(title, version, lic, texts):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", title)
    path = os.path.join(OUT_DIR, f"{safe}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"{title} {version}\nLicence: {lic}\n{'=' * 72}\n\n")
        for name, text in texts:
            fh.write(f"--- {name} ---\n{text.strip()}\n\n")
        if not texts:
            fh.write("(No licence file ships with this package; see its home page.)\n")
    return path


def main():
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    os.makedirs(OUT_DIR)
    rows = []

    for dist in dependencies(TOP_LEVEL):
        meta = dist.metadata
        title, version = meta["Name"], dist.version
        lic = licence_name(meta)
        write_license_file(title, version, lic, licence_texts(dist))
        rows.append((title, version, lic, home_page(meta)))

    # PyInstaller's bootloader (only present where it is installed, i.e. the build machine)
    try:
        pi = metadata.distribution("pyinstaller")
        write_license_file("PyInstaller", pi.version, "GPL-2.0-or-later with bootloader exception", licence_texts(pi))
        rows.append(("PyInstaller (bootloader)", pi.version, "GPL-2.0-or-later with the bootloader exception",
                     "https://pyinstaller.org/"))
    except metadata.PackageNotFoundError:
        pass

    # fonts and the rest
    inter = os.path.join(ROOT, "assets", "fonts", "Inter-LICENSE.txt")
    if os.path.isfile(inter):
        shutil.copy(inter, os.path.join(OUT_DIR, "Inter.txt"))
    try:
        import matplotlib
        dj = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "LICENSE_DEJAVU")
        if os.path.isfile(dj):
            shutil.copy(dj, os.path.join(OUT_DIR, "DejaVu_fonts.txt"))
    except ImportError:
        pass
    py_lic = os.path.join(sys.base_prefix, "LICENSE.txt")
    if os.path.isfile(py_lic):
        shutil.copy(py_lic, os.path.join(OUT_DIR, "Python.txt"))
    for tcl in (os.path.join(sys.base_prefix, "tcl", "tcl8.6", "license.terms"),
                os.path.join(sys.base_prefix, "tcl", "tk8.6", "license.terms")):
        if os.path.isfile(tcl):
            shutil.copy(tcl, os.path.join(OUT_DIR, "Tcl_Tk.txt"))
            break

    rows = [(n, v, l, u) for n, v, l, u in EXTRA] + sorted(rows, key=lambda r: r[0].lower())
    with open(NOTICES, "w", encoding="utf-8") as fh:
        fh.write("# Third-party notices\n\n")
        fh.write("Contour Map Generator is free to use, and its own code is public to read but not open source "
                 "(all rights reserved, see TERMS.md). It is built on the "
                 "open-source components below, each under its own licence. Those licences apply to those "
                 "components, not to Contour Map Generator's own code.\n\n")
        fh.write("The full licence texts are in the `licenses` folder next to the app, and in the app under "
                 "Help, Third-party licences.\n\n")
        fh.write("| Component | Version | Licence | Source |\n|---|---|---|---|\n")
        for n, v, l, u in rows:
            fh.write(f"| {n} | {v} | {l} | {u} |\n")
        notes = [(n, NOTES[n]) for n, *_ in rows if n in NOTES]
        if notes:
            fh.write("\n## Notes\n\n")
            for n, t in notes:
                fh.write(f"- **{n}:** {t}\n")
    print(f"{len(rows)} components, {len(os.listdir(OUT_DIR))} licence files")


if __name__ == "__main__":
    main()
