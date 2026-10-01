"""Background execution of a batch. Tk-free: the GUI polls `poll()` from an `after()` timer.

Worker threads never touch widgets; they only append events to a queue.
"""
import queue
import threading
from typing import List, Optional, Tuple

from .runner import RunConfig, SheetResult, run_batch


class BatchWorker:
    """Runs run_batch() on a daemon thread.

    Events returned by poll():
      ("progress", i, total, sheet)
      ("result", SheetResult)
      ("done", List[SheetResult], cancelled: bool)
      ("crash", message)            # unexpected failure outside any single sheet
    """

    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, name="contour-batch", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        """Stop after the sheet that is currently being drawn."""
        self._cancel.set()

    @property
    def running(self) -> bool:
        return self._thread.is_alive()

    def poll(self) -> List[tuple]:
        events = []
        while True:
            try:
                events.append(self._q.get_nowait())
            except queue.Empty:
                return events

    def _run(self) -> None:
        try:
            results = run_batch(
                self.cfg,
                on_progress=lambda i, n, sheet: self._q.put(("progress", i, n, sheet)),
                on_result=lambda r: self._q.put(("result", r)),
                cancel=self._cancel,
            )
            self._q.put(("done", results, self._cancel.is_set()))
        except Exception as e:                       # should not happen: sheets are isolated
            self._q.put(("crash", f"{type(e).__name__}: {e}"))
