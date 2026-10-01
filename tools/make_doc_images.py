"""Regenerate the pictures in docs/ from the real app (needs a display; use xvfb-run on Linux).

    xvfb-run -a -s "-screen 0 1500x1000x24" python tools/make_doc_images.py
"""
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw, ImageFont, ImageGrab                  # noqa: E402

DOCS = os.path.join(ROOT, "docs")


def main():
    from tkinter import filedialog

    from contourmap import branding, dialogs
    from contourmap.gui import App
    from contourmap.settings import SettingsStore
    from contourmap.theme import C

    work = tempfile.mkdtemp()
    sample = os.path.join(work, "sample_multisheet.xlsx")
    shutil.copy(os.path.join(ROOT, "sample_data", "sample_multisheet.xlsx"), sample)
    filedialog.askopenfilename = lambda **k: sample
    os.makedirs(DOCS, exist_ok=True)

    app = App(SettingsStore(os.path.join(work, "s.json")))
    app.geometry("1260x860+0+0")

    def pump(sec, until=None):
        t0 = time.time()
        while time.time() - t0 < sec:
            app.update()
            if until and until():
                break
            time.sleep(0.02)

    def grab(win, name):
        win.update()
        x, y, w, h = win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h), xdisplay=os.environ["DISPLAY"]).save(os.path.join(DOCS, name))

    pump(0.5)
    app.open_file()
    pump(0.5)
    app.cmap_var.set("viridis")
    app.ptabs.select("map")
    pump(10, lambda: app.mapview.canvas is not None)
    pump(1.0)
    grab(app, "main-window.png")

    # the Help menu, open
    app.help_menu.post(app.help_btn.winfo_rootx(), app.help_btn.winfo_rooty() + app.help_btn.winfo_height() + 4)
    pump(0.6)
    x, y = app.help_btn.winfo_rootx() - 260, app.help_btn.winfo_rooty() - 10
    ImageGrab.grab(bbox=(x, y, x + 520, y + 360), xdisplay=os.environ["DISPLAY"]).save(os.path.join(DOCS, "help-menu.png"))
    app.help_menu.unpost()

    about = dialogs.AboutDialog(app, lambda: None, lambda: None, lambda: None)
    about.geometry("+80+40")
    pump(0.6)
    grab(about, "about.png")
    about.destroy()

    # a finished map, as the app saves it
    from contourmap.session import UserOptions, make_run_config
    from contourmap.runner import run_batch
    out = os.path.join(work, "out")
    os.makedirs(out)
    opts = UserOptions(sheets=["Survey A"], output_dir=out, cmap="viridis", dpi=150, title="Survey A",
                       on_exists="overwrite")
    run_batch(make_run_config(app.session, opts))
    shutil.copy(os.path.join(out, "Survey A.png"), os.path.join(DOCS, "sample-map.png"))
    app.destroy()

    # social preview 1280 x 640
    W, H = 1280, 640
    img = Image.new("RGB", (W, H), C.bg)
    d = ImageDraw.Draw(img)
    for i in range(H):                                  # soft top-right glow
        pass
    fonts = os.path.join(ROOT, "assets", "fonts")
    f_big = ImageFont.truetype(os.path.join(fonts, "Inter-Bold.otf"), 62)
    f_mid = ImageFont.truetype(os.path.join(fonts, "Inter-Regular.otf"), 30)
    f_small = ImageFont.truetype(os.path.join(fonts, "Inter-Regular.otf"), 24)
    logo = Image.open(branding.logo_path()).convert("RGBA").resize((96, 96), Image.LANCZOS)
    mask = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 95, 95), radius=18, fill=255)
    img.paste(logo, (72, 72), mask)
    d.text((72, 210), "Contour Map\nGenerator", font=f_big, fill=C.text, spacing=6)
    d.text((72, 372), "X / Y / Z data to contour maps.\nExcel, CSV and text files.", font=f_mid, fill=C.muted, spacing=8)
    d.rectangle((72, 482, 116, 484), fill=C.accent)
    d.text((132, 468), "FREE FOR WINDOWS", font=f_small, fill=C.accent_pale)
    m = Image.open(os.path.join(DOCS, "sample-map.png")).convert("RGB")
    m.thumbnail((620, 520))
    card = Image.new("RGB", (m.width + 24, m.height + 24), C.card)
    card.paste(m, (12, 12))
    img.paste(card, (W - card.width - 64, (H - card.height) // 2))
    img.save(os.path.join(DOCS, "social-preview.png"))
    print("wrote", sorted(os.listdir(DOCS)))


if __name__ == "__main__":
    main()
