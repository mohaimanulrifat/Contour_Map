# -*- mode: python ; coding: utf-8 -*-
# One spec, two builds:   CMG_ONEFILE=1  -> a single portable .exe
#                         (unset / 0)    -> a folder (exe + _internal), used for the zip
# Normally run through tools/build_release.py (or build.bat), not directly.
import os
import sys

ONEFILE = os.environ.get("CMG_ONEFILE") == "1"
NAME = "ContourMapGenerator"
VERSION_FILE = os.environ.get("CMG_VERSION_FILE")
if not (VERSION_FILE and os.path.isfile(VERSION_FILE) and sys.platform == "win32"):
    VERSION_FILE = None

# things this app never uses; leaving them out keeps the download smaller
EXCLUDES = [
    "IPython", "jupyter", "notebook", "pytest", "setuptools", "pkg_resources", "distutils",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "gi", "cairo", "tornado", "docutils", "sphinx",
    "matplotlib.backends.backend_qt", "matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_qt5",
    "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_gtk3", "matplotlib.backends.backend_gtk4",
    "matplotlib.backends.backend_wx", "matplotlib.backends.backend_webagg", "matplotlib.backends.backend_nbagg",
    "matplotlib.backends.backend_macosx", "matplotlib.tests", "numpy.tests", "pandas.tests", "scipy.tests",
]

a = Analysis(
    ["ContourMapGenerator.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets"), ("TERMS.md", "."), ("THIRD_PARTY_NOTICES.md", "."), ("licenses", "licenses")],
    hiddenimports=["openpyxl", "xlrd", "scipy.spatial", "PIL._tkinter_finder",
                   "matplotlib.backends.backend_agg", "matplotlib.backends.backend_pdf",
                   "matplotlib.backends.backend_svg", "matplotlib.backends.backend_ps",
                   "matplotlib.backends.backend_tkagg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
# matplotlib's bundled sample data (tens of MB) is never read by this app
a.datas = [d for d in a.datas if "mpl-data/sample_data" not in d[0].replace("\\", "/")]

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name=NAME, debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
        runtime_tmpdir=None, console=False, disable_windowed_traceback=False,
        icon="assets/app.ico", version=VERSION_FILE,
    )
else:
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True,
        name=NAME, debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
        console=False, disable_windowed_traceback=False,
        icon="assets/app.ico", version=VERSION_FILE,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)
