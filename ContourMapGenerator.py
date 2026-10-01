"""Contour Map Generator -- entry point (used by PyInstaller and `python ContourMapGenerator.py`)."""
import sys

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":      # used by the release build
        from contourmap.selftest import run
        sys.exit(run(sys.argv[2] if len(sys.argv) > 2 else None))
    from contourmap.gui import main
    main()
