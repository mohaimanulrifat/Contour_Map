"""'Check for updates': asks GitHub for the latest release. Runs only when the user clicks.

No data about the user is sent; the request is a plain GET of the public release page data.
"""
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from . import branding
from .version import VERSION


class UpdateError(Exception):
    """The check could not be completed (message is safe to show)."""


@dataclass
class UpdateResult:
    status: str                 # "newer" | "current" | "ahead"
    current: str
    latest: str
    url: str = branding.RELEASES_URL
    notes: str = ""


def parse_version(text: str) -> Tuple[int, ...]:
    """'v1.2.10' -> (1, 2, 10). Anything after the numbers (e.g. '-beta') is ignored."""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", str(text))
    if not m:
        raise ValueError(f"not a version: {text!r}")
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    width = max(len(a), len(b))
    pad = lambda t: t + (0,) * (width - len(t))
    return pad(a) > pad(b)


def fetch_latest(api_url: str = branding.LATEST_RELEASE_API, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(api_url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{branding.EXE_NAME}/{VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise UpdateError("No public release was found yet. Try again later, or look at the "
                              "download page.")
        if e.code in (403, 429):
            raise UpdateError("GitHub is limiting requests right now. Please try again in a while.")
        raise UpdateError(f"The update server answered with an error ({e.code}).")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise UpdateError("Could not reach the update server. Check your internet connection.")
    except ValueError:
        raise UpdateError("The update server sent an answer this app does not understand.")


def check(current: str = VERSION, fetch: Callable[[], dict] = fetch_latest) -> UpdateResult:
    """Compare the running version with the latest release. Raises UpdateError."""
    data = fetch()
    tag = str(data.get("tag_name") or data.get("name") or "")
    try:
        newer = is_newer(tag, current)
        same = parse_version(tag) == parse_version(current)
    except ValueError:
        raise UpdateError("The latest release has a version number this app cannot read.")
    status = "newer" if newer else "current" if same else "ahead"
    return UpdateResult(status, current, tag.lstrip("v"), data.get("html_url") or branding.RELEASES_URL,
                        (data.get("body") or "").strip())
