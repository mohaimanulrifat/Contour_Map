# What changed

## 1.0.0, 1 October 2026

The first release.

- Turns X / Y / Z data from Excel (.xlsx, .xls), CSV and text files into contour map images, one image per sheet.
- **Data:** column format or grid / matrix format, "use first row as column titles", skip rows at the top and bottom, and X / Y / Z column pickers with a live check of how many rows are valid. CSV and text files are read whatever the delimiter, encoding or decimal comma.
- **Plot:** linear, cubic or nearest interpolation, grid resolution, mask outside the data hull, filled / lines / both, a number of levels or your own minimum, maximum and step, 33 colormaps with reverse, contour labels, data points, grid lines, colorbar, equal aspect ratio, inverted axes, axis limits, font size and figure size.
- **Labels:** title, axis names and colorbar label, filled in from your column titles.
- **Output:** PNG, JPG, PDF, SVG and TIFF at 72, 150, 300 or 600 DPI, with an optional transparent background. Images are named after their sheets, with an optional prefix, suffix or custom name. Windows-unsafe characters are replaced, and nothing is overwritten without asking unless you choose to.
- **Live map preview** inside the window, with pan, zoom and reset, for the sheet you are looking at.
- Several sheets are made in one run, in the background, with a progress bar and a Cancel button. A sheet that fails never stops the others, and the results box says why.
- Remembers your settings between runs.
- Help menu: how to use, suggestions, problem reports, an update check that runs only when you click it, the settings folder, third-party licences, the terms of use and About.
- Everything needed is inside the app. Nothing to install.
