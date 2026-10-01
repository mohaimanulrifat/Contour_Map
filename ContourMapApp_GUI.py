import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import os
import threading
import re

def find_xyz_columns(df):
    """
    Try to locate x, y, z columns in dataframe by name (case-insensitive).
    If names are not found, fall back to first 3 columns (by position).
    Returns (x_col_name, y_col_name, z_col_name, label_x, label_y, label_z)
    where label_* are the strings to use for axis/colorbar (header text).
    """
    cols = list(df.columns)
    lower = [str(c).strip().lower() for c in cols]

    # match rules: exact 'x','y','z' or startswith 'x', 'y', 'z', or contains ' x' or 'x ' or '(x)'
    def match_index(prefix):
        for i, name in enumerate(lower):
            if name == prefix:
                return i
        for i, name in enumerate(lower):
            if name.startswith(prefix):
                return i
        # also look for patterns like '(x)', ' x)', ' x '
        pattern = re.compile(r'(^|[^a-z0-9])' + re.escape(prefix) + r'([^a-z0-9]|$)')
        for i, name in enumerate(lower):
            if pattern.search(name):
                return i
        return None

    xi = match_index('x')
    yi = match_index('y')
    zi = match_index('z')

    # Avoid duplicates: if matched same column for multiple axes, discard those matches
    if xi is not None and yi is not None and xi == yi:
        yi = None
    if xi is not None and zi is not None and xi == zi:
        zi = None
    if yi is not None and zi is not None and yi == zi:
        zi = None

    # If any missing, try to find columns containing 'long', 'lat' etc? (skip for now)
    # Fallback: use first 3 columns by position if any of xi,yi,zi is None
    if xi is None or yi is None or zi is None:
        if len(cols) >= 3:
            x_col, y_col, z_col = cols[0], cols[1], cols[2]
        else:
            # not enough columns
            return (None, None, None, None, None, None)
    else:
        x_col, y_col, z_col = cols[xi], cols[yi], cols[zi]

    # Labels will be the header strings (exact text)
    label_x = str(x_col)
    label_y = str(y_col)
    label_z = str(z_col)
    return (x_col, y_col, z_col, label_x, label_y, label_z)


def generate_contour():
    file_path = filedialog.askopenfilename(
        title="Select CSV or Excel file",
        filetypes=[("Data Files", "*.csv *.xlsx *.xls"), ("All Files", "*.*")]
    )
    if not file_path:
        messagebox.showinfo("Info", "No file selected.")
        return

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".csv":
            # read CSV (pandas will read header if present)
            data_dict = {"Sheet1": pd.read_csv(file_path)}
        elif ext in [".xlsx", ".xls"]:
            xls = pd.ExcelFile(file_path)
            data_dict = {sheet: xls.parse(sheet) for sheet in xls.sheet_names}
        else:
            messagebox.showerror("Error", "Unsupported file type.")
            return
    except Exception as e:
        messagebox.showerror("Error", f"Problem reading file:\n{e}")
        return

    total_sheets = len(data_dict)
    progress_bar["maximum"] = total_sheets
    progress_bar["value"] = 0
    status_label.config(text="Starting map generation...")
    root.update_idletasks()

    def process_sheets():
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        save_dir = os.path.dirname(file_path)
        saved_files = []

        for i, (sheet_name, data) in enumerate(data_dict.items(), start=1):
            try:
                # Ensure dataframe has at least 3 columns
                if data.shape[1] < 3:
                    status_label.config(text=f"⚠️ Skipped: {sheet_name} (less than 3 columns)")
                    root.update_idletasks()
                    progress_bar["value"] = i
                    continue

                # Clean column names (strip whitespace)
                data.columns = [str(c).strip() for c in data.columns]

                # Find x,y,z columns and readable labels
                x_col, y_col, z_col, label_x, label_y, label_z = find_xyz_columns(data)
                if x_col is None or y_col is None or z_col is None:
                    status_label.config(text=f"⚠️ Skipped: {sheet_name} (couldn't determine x,y,z)")
                    root.update_idletasks()
                    progress_bar["value"] = i
                    continue

                # extract series
                x = pd.to_numeric(data[x_col], errors='coerce')
                y = pd.to_numeric(data[y_col], errors='coerce')
                z = pd.to_numeric(data[z_col], errors='coerce')

                # drop rows with NaN in x,y,z
                df_xyz = pd.DataFrame({ 'x': x, 'y': y, 'z': z }).dropna()
                if df_xyz.empty:
                    status_label.config(text=f"⚠️ Skipped: {sheet_name} (no numeric x/y/z data)")
                    root.update_idletasks()
                    progress_bar["value"] = i
                    continue

                x = df_xyz['x'].values
                y = df_xyz['y'].values
                z = df_xyz['z'].values

                # Create grid for interpolation
                xi = np.linspace(np.min(x), np.max(x), 200)
                yi = np.linspace(np.min(y), np.max(y), 200)
                X, Y = np.meshgrid(xi, yi)
                # Use 'linear' fallback if cubic fails for small datasets
                try:
                    Z = griddata((x, y), z, (X, Y), method='cubic')
                    if np.isnan(Z).all():
                        Z = griddata((x, y), z, (X, Y), method='linear')
                except Exception:
                    Z = griddata((x, y), z, (X, Y), method='linear')

                # Plot
                plt.figure(figsize=(8, 7))
                contour = plt.contourf(X, Y, Z, levels=15, cmap='plasma')
                plt.colorbar(contour, label='Corrosion Potential (V)')
                lines = plt.contour(X, Y, Z, levels=15, colors='k', linewidths=0.5)
                plt.clabel(lines, inline=True, fontsize=8, fmt='%.3f')
                plt.title('Contour Map Based on ASTM C876-15')
                plt.xlabel(f'{label_x}')
                plt.ylabel(f'{label_y}')
                plt.grid(True)

                # Save file using sheet name
                # Use safe filename for sheet (replace forbidden characters)
                safe_sheet = "".join(c if c.isalnum() or c in " _-" else "_" for c in str(sheet_name))
                save_name = f"{base_name}_{safe_sheet}.png"
                save_path = os.path.join(save_dir, save_name)
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                saved_files.append(save_path)

                progress_bar["value"] = i
                status_label.config(text=f"✅ Saved: {sheet_name} ({i}/{total_sheets})")
                root.update_idletasks()

            except Exception as e:
                status_label.config(text=f"⚠️ Error in {sheet_name}: {e}")
                root.update_idletasks()
                progress_bar["value"] = i
                continue

        if saved_files:
            # open folder optionally - commented by default
            # os.startfile(save_dir)
            messagebox.showinfo("Done", f"Contour maps saved:\n\n" + "\n".join(saved_files))
            status_label.config(text="✅ All maps generated successfully!")
        else:
            status_label.config(text="No contour maps were generated.")
            messagebox.showinfo("Info", "No contour maps were generated.")

    threading.Thread(target=process_sheets).start()


# === GUI Setup ===
root = tk.Tk()
root.title("Contour Map Generator")
root.geometry("420x260")

label = tk.Label(root, text="Generate Contour Maps from CSV or Excel Data",
                 font=("Segoe UI", 11, "bold"))
label.pack(pady=12)

btn = tk.Button(root, text="Open File and Generate Maps", command=generate_contour,
                bg="#4FC3F7", fg="black", font=("Segoe UI", 10, "bold"),
                padx=20, pady=6)
btn.pack(pady=8)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=340, mode="determinate")
progress_bar.pack(pady=10)

status_label = tk.Label(root, text="Status: Waiting for input...", font=("Segoe UI", 9))
status_label.pack(pady=6)

note_label = tk.Label(root, text="Header names (A1,B1,C1) will be used as axis labels.\nIf no x/y/z names found, the first 3 columns are used.",
                      font=("Segoe UI", 8), justify="center")
note_label.pack(pady=4)

quit_btn = tk.Button(root, text="Exit", command=root.quit)
quit_btn.pack(pady=6)

root.mainloop()
