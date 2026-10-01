"""Contour Map Generator -- entry point.

The application code lives in the `contourmap` package; this file is kept as the
launcher so build.bat / ContourMapApp.spec (PyInstaller) keep working unchanged.
"""
from contourmap.gui import main

if __name__ == "__main__":
    main()
