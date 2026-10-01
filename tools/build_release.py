"""Build the release files: a zip with the app folder, and one portable single-file exe.

    python tools/build_release.py [--licenses] [--skip-onefile] [--skip-onedir]

Run it on Windows for the real thing (it also works on Linux/macOS for a dry run). Output goes
to release/ :
    ContourMapGenerator-<version>-win64.zip      folder build + sample data + docs + licences
    ContourMapGenerator-<version>-portable.exe   single file
    SHA256SUMS.txt
"""
import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from contourmap import branding                                   # noqa: E402
from contourmap.version import VERSION                            # noqa: E402

NAME = branding.EXE_NAME
WIN = sys.platform == "win32"
EXE = NAME + (".exe" if WIN else "")
PLATFORM = "win64" if WIN else sys.platform
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(ROOT, "release")


def run(cmd, env=None):
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def write_build_info():
    path = os.path.join(ROOT, "contourmap", "build_info.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f'BUILD_DATE = "{datetime.date.today().isoformat()}"\n')


def write_version_file() -> str:
    """Windows 'Details' tab of the exe: product name, version, copyright."""
    if not WIN:
        return ""
    os.makedirs(BUILD, exist_ok=True)
    nums = tuple((int(p) for p in (VERSION.split(".") + ["0"] * 4)[:4]))
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{branding.AUTHOR}'),
      StringStruct('FileDescription', '{branding.APP_NAME}'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('LegalCopyright', '{branding.COPYRIGHT}'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', '{branding.APP_NAME}'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = os.path.join(BUILD, "file_version_info.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def pyinstaller(onefile: bool, version_file: str):
    env = dict(os.environ, CMG_ONEFILE="1" if onefile else "0", CMG_VERSION_FILE=version_file)
    sub = "onefile" if onefile else "onedir"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", os.path.join(DIST, sub), "--workpath", os.path.join(BUILD, sub),
         "ContourMapGenerator.spec"], env=env)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_zip(zip_path):
    folder = f"{NAME}-{VERSION}"
    app_dir = os.path.join(DIST, "onedir", NAME)
    extras = [("sample_data", "sample_data"), ("licenses", "licenses"), ("README.md", "README.md"),
              ("TERMS.md", "TERMS.md"), ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
              ("CHANGELOG.md", "CHANGELOG.md")]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        def add_tree(src, arc):
            for base, _dirs, files in os.walk(src):
                for f in files:
                    full = os.path.join(base, f)
                    z.write(full, os.path.join(folder, arc, os.path.relpath(full, src)))
        add_tree(app_dir, "")
        for src, arc in extras:
            full = os.path.join(ROOT, src)
            if os.path.isdir(full):
                add_tree(full, arc)
            elif os.path.isfile(full):
                z.write(full, os.path.join(folder, arc))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--licenses", action="store_true", help="regenerate the third-party notices first")
    ap.add_argument("--skip-onefile", action="store_true")
    ap.add_argument("--skip-onedir", action="store_true")
    args = ap.parse_args()

    if args.licenses:
        run([sys.executable, "tools/make_licenses.py"])
    write_build_info()
    vf = write_version_file()
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    sums = []

    if not args.skip_onedir:
        pyinstaller(False, vf)
        zip_path = os.path.join(OUT, f"{NAME}-{VERSION}-{PLATFORM}.zip")
        make_zip(zip_path)
        sums.append(zip_path)
    if not args.skip_onefile:
        pyinstaller(True, vf)
        portable = os.path.join(OUT, f"{NAME}-{VERSION}-portable" + (".exe" if WIN else ""))
        shutil.copy(os.path.join(DIST, "onefile", EXE), portable)
        sums.append(portable)

    with open(os.path.join(OUT, "SHA256SUMS.txt"), "w", encoding="utf-8") as fh:
        for p in sums:
            fh.write(f"{sha256(p)}  {os.path.basename(p)}\n")
    print("\nBuilt:")
    for p in sums:
        print(f"  {os.path.basename(p):55s} {os.path.getsize(p) / 1e6:7.1f} MB")


if __name__ == "__main__":
    main()
