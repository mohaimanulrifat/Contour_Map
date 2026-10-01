"""Names, links and bundled-resource lookup. Edit this file to rebrand the app.

APP_NAME   shown in the title bar, the header and About.
LOGO_FILE  looked up in assets/ next to the app; if missing, the header shows just the name.
"""
import os
import sys

from .version import VERSION

APP_NAME = "Contour Map Generator"
APP_TAGLINE = "Turn X / Y / Z data into contour maps"
APP_SUMMARY = ("Turns X / Y / Z data from Excel, CSV and text files into contour map images, "
               "one per sheet, with full control over the columns, interpolation and styling.")
LOGO_FILE = "logo.png"
ICON_FILE = "app.ico"
EXE_NAME = "ContourMapGenerator"

# --- the author ---------------------------------------------------------------------------
AUTHOR = "Mohaimanul Islam Rifat"
AUTHOR_SHORT = "Rifat"
AUTHOR_ROLE = "Media professional from Dhaka, Bangladesh"
LINKEDIN_URL = "https://www.linkedin.com/in/md-mohaimanul-islam"
GITHUB_PROFILE_URL = "https://github.com/mohaimanulrifat"
EMAIL = "mohaimanul.islam@outlook.com"
COPYRIGHT = f"© 2026 {AUTHOR}. All rights reserved."

# --- where releases, suggestions and problem reports live ---------------------------------
# Change REPO if the public downloads live in a different repository.
REPO = "mohaimanulrifat/Contour_Map"
REPO_URL = f"https://github.com/{REPO}"
RELEASES_URL = f"{REPO_URL}/releases/latest"
SUGGESTION_URL = f"{REPO_URL}/issues/new?template=suggestion.yml"
PROBLEM_URL = f"{REPO_URL}/issues/new?template=bug_report.yml"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"


def resource_path(*parts: str) -> str:
    """Path of a bundled resource, both from source and from the PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def logo_path():
    p = resource_path("assets", LOGO_FILE)
    return p if os.path.isfile(p) else None


def title_with_version() -> str:
    return f"{APP_NAME} {VERSION}"
