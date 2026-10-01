"""Embedded map preview: a matplotlib canvas with pan / zoom / reset, rendered off the GUI thread.

MapView.request(builder) is called (often, e.g. while the user types); renders are debounced by
the caller and run one at a time here: if a newer request arrives while one is running, only the
newest is rendered afterwards. The builder runs on a worker thread and must not touch widgets.
"""
import queue
import threading
import tkinter as tk
from typing import Callable, Optional, Tuple

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .data_loader import DataLoadError, SheetSkipped
from .engine import PlotError
from .theme import C, PillButton, font, px

Builder = Callable[[], Tuple[Figure, str]]       # -> (figure, one-line info)


class MapView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=C.card)
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.toolbar: Optional[NavigationToolbar2Tk] = None
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._busy = False
        self._pending: Optional[Builder] = None
        self._latest = 0
        self._alive = True

        bar = tk.Frame(self, bg=C.card)
        bar.pack(fill="x", pady=(0, px(8)))
        self.btn = {}
        for key, text, style, cmd in (("home", "Reset view", "ghost", lambda: self._tool("home")),
                                      ("back", "Back", "ghost", lambda: self._tool("back")),
                                      ("forward", "Forward", "ghost", lambda: self._tool("forward")),
                                      ("pan", "Pan", "secondary", lambda: self._tool("pan")),
                                      ("zoom", "Zoom", "secondary", lambda: self._tool("zoom")),
                                      ("save", "Save image…", "secondary", lambda: self._tool("save_figure"))):
            b = PillButton(bar, text, cmd, style=style, bg=C.card, padx=14, height=28)
            b.pack(side="left", padx=(0, px(6)))
            b.set_enabled(False)
            self.btn[key] = b
        self.coords = tk.StringVar()
        tk.Label(bar, textvariable=self.coords, bg=C.card, fg=C.dim, font=font(9)).pack(side="right")

        self.info = tk.StringVar()                  # packed first so it always keeps its line
        tk.Label(self, textvariable=self.info, bg=C.card, fg=C.muted, font=font(9), anchor="w").pack(
            side="bottom", fill="x", pady=(px(6), 0))
        self.holder = tk.Frame(self, bg=C.input)
        self.holder.pack(fill="both", expand=True)
        self.msg = tk.Label(self.holder, text="", bg=C.input, fg=C.muted, font=font(10),
                            wraplength=px(420), justify="center")
        self.msg.place(relx=0.5, rely=0.5, anchor="center")
        self.after(60, self._poll)

    # ---------------------------------------------------------------- public
    def show_message(self, text: str, kind: str = "info") -> None:
        """Replace the map by a message ('info', 'error' or 'busy')."""
        self._latest += 1                         # drop any render still in flight
        self._pending = None
        self._clear_canvas()
        self.msg.config(text=text, fg={"error": C.err, "busy": C.accent_pale}.get(kind, C.muted))
        self.msg.place(relx=0.5, rely=0.5, anchor="center")
        self.info.set("")

    def request(self, builder: Builder) -> None:
        self._latest += 1
        if self._busy:
            self._pending = builder                # run after the current one finishes
        else:
            self._start(builder, self._latest)
        self.info.set("Drawing the map…")

    def destroy(self):
        self._alive = False
        super().destroy()

    # ---------------------------------------------------------------- worker
    def _start(self, builder: Builder, token: int) -> None:
        self._busy = True

        def work():
            try:
                fig, info = builder()
                self._q.put((token, "ok", fig, info))
            except SheetSkipped as e:
                self._q.put((token, "info", f"This sheet can't be mapped: {e}.", ""))
            except (PlotError, DataLoadError) as e:
                self._q.put((token, "error", str(e).strip(), ""))
            except Exception as e:                  # never let the preview crash the app
                self._q.put((token, "error", f"{type(e).__name__}: {e}", ""))
        threading.Thread(target=work, name="map-preview", daemon=True).start()

    def _poll(self):
        if not self._alive:
            return
        try:
            while True:
                token, kind, payload, info = self._q.get_nowait()
                self._busy = False
                if self._pending is not None:
                    builder, self._pending = self._pending, None
                    self._start(builder, self._latest)
                elif token == self._latest:
                    if kind == "ok":
                        self._display(payload, info)
                    else:
                        self.show_message(payload, kind)
        except queue.Empty:
            pass
        self.after(60, self._poll)

    # ---------------------------------------------------------------- canvas
    def _display(self, fig: Figure, info: str) -> None:
        self._clear_canvas()
        self.msg.place_forget()
        self.canvas = FigureCanvasTkAgg(fig, master=self.holder)
        self.canvas.mpl_connect("resize_event", lambda e, f=fig: self._fit_labels(f))
        # the stock toolbar does the mouse handling; it is never shown, our buttons drive it
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.holder, pack_toolbar=False)
        self.toolbar.message.trace_add("write", lambda *a: self.coords.set(self.toolbar.message.get()))
        widget = self.canvas.get_tk_widget()
        widget.configure(highlightthickness=0, bd=0, width=px(120), height=px(120))   # size comes from the layout
        widget.pack(fill="both", expand=True)
        self.canvas.draw_idle()
        for b in self.btn.values():
            b.set_enabled(True)
            b.set_active(False)
        self.info.set(info)

    @staticmethod
    def _fit_labels(fig: Figure) -> None:
        """Keep axis labels inside the pane whatever its size (saved files use a tight bounding box)."""
        try:
            fig.tight_layout(pad=0.8)
        except Exception:
            pass

    def _clear_canvas(self) -> None:
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
            if self.toolbar is not None:
                self.toolbar.destroy()
            self.canvas = self.toolbar = None
        self.coords.set("")
        for b in self.btn.values():
            b.set_enabled(False)
            b.set_active(False)

    def _tool(self, name: str) -> None:
        if self.toolbar is None:
            return
        getattr(self.toolbar, name)()
        mode = getattr(self.toolbar.mode, "name", str(self.toolbar.mode)).upper()
        self.btn["pan"].set_active("PAN" in mode)
        self.btn["zoom"].set_active("ZOOM" in mode)
