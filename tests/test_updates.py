import json
import urllib.error

import pytest

from contourmap import updates
from contourmap.updates import UpdateError, check, is_newer, parse_version


@pytest.mark.parametrize("text,expected", [("1.0.0", (1, 0, 0)), ("v1.2.10", (1, 2, 10)), ("2", (2,)),
                                           ("v1.1.0-beta", (1, 1, 0))])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_parse_version_rejects_garbage():
    with pytest.raises(ValueError):
        parse_version("latest")


@pytest.mark.parametrize("latest,current,newer", [("1.0.1", "1.0.0", True), ("1.10.0", "1.9.0", True),
                                                  ("v2.0", "1.9.9", True), ("1.0.0", "1.0.0", False),
                                                  ("1.0", "1.0.0", False), ("0.9.0", "1.0.0", False)])
def test_is_newer(latest, current, newer):
    assert is_newer(latest, current) is newer


def fake(data):
    return lambda: data


def test_check_statuses():
    assert check("1.0.0", fake({"tag_name": "v1.1.0", "html_url": "http://x"})).status == "newer"
    assert check("1.0.0", fake({"tag_name": "v1.0.0"})).status == "current"
    assert check("1.2.0", fake({"tag_name": "v1.1.0"})).status == "ahead"
    r = check("1.0.0", fake({"tag_name": "v1.1.0", "html_url": "http://x", "body": " notes "}))
    assert (r.latest, r.url, r.notes) == ("1.1.0", "http://x", "notes")


def test_check_unreadable_version():
    with pytest.raises(UpdateError):
        check("1.0.0", fake({"tag_name": "nightly"}))


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def read(self): return self.payload
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_fetch_latest_errors_are_friendly(monkeypatch):
    def raising(exc):
        def _open(req, timeout=None): raise exc
        return _open
    for exc, text in [(urllib.error.HTTPError("u", 404, "nf", {}, None), "No public release"),
                      (urllib.error.HTTPError("u", 403, "rl", {}, None), "limiting"),
                      (urllib.error.HTTPError("u", 500, "x", {}, None), r"error \(500\)"),
                      (urllib.error.URLError("offline"), "Could not reach")]:
        monkeypatch.setattr(updates.urllib.request, "urlopen", raising(exc))
        with pytest.raises(UpdateError, match=text):
            updates.fetch_latest()
    monkeypatch.setattr(updates.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse(b"not json"))
    with pytest.raises(UpdateError, match="does not understand"):
        updates.fetch_latest()
    monkeypatch.setattr(updates.urllib.request, "urlopen",
                        lambda req, timeout=None: FakeResponse(json.dumps({"tag_name": "v9.9.9"}).encode()))
    assert updates.fetch_latest()["tag_name"] == "v9.9.9"
