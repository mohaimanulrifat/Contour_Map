"""Last-used settings, stored per mode in a small JSON file next to the app.

If the app folder is not writable (e.g. installed under Program Files) the file is kept in
the user's profile instead. A missing or corrupt file is never an error: defaults are used.
"""
import json
import os
import sys
from typing import Any, Dict, List

FILE_NAME = "contour_settings.json"


def app_dir() -> str:
    """Folder of the .exe when frozen by PyInstaller, else the project folder."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fallback_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "ContourMapApp")


def candidate_paths() -> List[str]:
    return [os.path.join(app_dir(), FILE_NAME), os.path.join(_fallback_dir(), FILE_NAME)]


class SettingsStore:
    """dict-like: top-level keys are shared values, `modes[<mode name>]` holds per-mode values."""

    def __init__(self, path: str = None):
        self._explicit = path
        self.data: Dict[str, Any] = {"modes": {}}
        self.load()

    # -- io ---------------------------------------------------------------------------
    def load(self) -> None:
        for p in ([self._explicit] if self._explicit else candidate_paths()):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    self.data = loaded
                    self.data.setdefault("modes", {})
                    if not isinstance(self.data["modes"], dict):
                        self.data["modes"] = {}
                    return
            except (OSError, ValueError):
                continue

    def save(self) -> bool:
        """Write the file; returns False if no location was writable."""
        for p in ([self._explicit] if self._explicit else candidate_paths()):
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                tmp = p + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, p)
                return True
            except OSError:
                continue
        return False

    # -- access -----------------------------------------------------------------------
    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value

    def mode(self, name: str) -> Dict[str, Any]:
        m = self.data["modes"].get(name)
        return m if isinstance(m, dict) else {}

    def set_mode(self, name: str, values: Dict[str, Any]) -> None:
        self.data["modes"][name] = dict(values)
