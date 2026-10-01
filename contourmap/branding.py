"""Where to put your own name and logo.

APP_NAME   shown in the title bar and the header.
LOGO_FILE  looked up in the assets/ folder next to the app; if the file is missing the header
           simply shows the name. A transparent PNG works best.
"""
import os
import sys

APP_NAME = "Contour Map Generator"
APP_TAGLINE = "Turn X / Y / Z data into contour maps"
LOGO_FILE = "logo.png"
ICON_FILE = "contour.ico"


def resource_path(*parts: str) -> str:
    """Path of a bundled resource, both when run from source and from the PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def logo_path():
    p = resource_path("assets", LOGO_FILE)
    return p if os.path.isfile(p) else None
