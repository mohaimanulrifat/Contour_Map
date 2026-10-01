# Building and releasing (for the maintainer)

Contour Map Generator is a Python / tkinter app packaged with PyInstaller. Two files are released
for every version: a **zip** (the app folder plus sample data, terms and licences) and a **portable
exe** (one file). Both are built on Windows, by GitHub Actions or on your own PC.

## Release a new version

1. Change `VERSION` in `contourmap/version.py` and add a `## x.y.z, date` section at the top of
   `CHANGELOG.md` (the release notes are taken from it).
2. Merge to `main`.
3. Tag and push: `git tag v1.0.1` then `git push origin v1.0.1`.

The **Build and release** workflow then runs the tests, builds both files on a Windows runner,
checks each one with `--selftest`, and publishes the release with `SHA256SUMS.txt`. A pull request
runs the same build without publishing; the files are under the run's *Artifacts*. To rehearse a
release, run the workflow by hand with *draft_release* ticked and review the draft.

## Build on your own PC

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-build.txt
build.bat
```

Output is in `release\`. Check a build with `ContourMapGenerator.exe --selftest result.txt`; the
file ends with `RESULT: ALL OK`.

## Your name, logo and links

- `contourmap/branding.py`: app name, author, links, and `REPO` (where "Check for updates",
  "Send a suggestion" and "Report a problem" point; the repository must be public for those to
  work for other people).
- `assets/logo.png` (header and About) and `assets/app.ico` (window and exe icon). To make the
  icon from a new logo: open the logo with Pillow and `save("assets/app.ico", sizes=[(16, 16),
  (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])`.
- The colours and fonts live in `contourmap/theme.py`.

## Third-party notices

`python tools/make_licenses.py` rewrites `THIRD_PARTY_NOTICES.md` and the `licenses` folder from
the packages installed in the current environment. The release build runs it automatically so the
notices match what is inside the app.

## Tests

`python -m pytest`. The window tests need a display and are skipped without one (on Linux, run
them with `xvfb-run -a python -m pytest`).

## Where things are

```
ContourMapGenerator.py     entry point (also `--selftest`)
ContourMapGenerator.spec   PyInstaller spec (folder build, or single file with CMG_ONEFILE=1)
contourmap/                the app (see the module docstrings)
tools/                     build_release.py, make_licenses.py, release_notes.py, make_sample_data.py
sample_data/               example workbook and CSV (also shipped in the zip)
assets/                    logo, icon, Inter font, the how-to text shown under Help
tests/                     unit and window tests
```
