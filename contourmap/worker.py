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
      ("ask_overwrite", path)       # GUI must answer with answer("overwrite"|"number"|"skip")
      ("result", SheetResult)
      ("done", List[SheetResult], cancelled: bool)
      ("crash", message)            # unexpected failure outside any single sheet
    """

    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._cancel = threading.Event()
        self._reply = threading.Event()
        self._reply_value = "skip"
        self._thread = threading.Thread(target=self._run, name="contour-batch", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        """Stop after the sheet that is currently being drawn."""
        self._cancel.set()

    def answer(self, choice: str) -> None:
        """Reply to an "ask_overwrite" event."""
        self._reply_value = choice
        self._reply.set()

    def _ask(self, path: str) -> str:
        self._reply.clear()
        self._q.put(("ask_overwrite", path))
        while not self._reply.wait(0.1):
            if self._cancel.is_set():
                return "skip"
        return self._reply_value

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
                ask_overwrite=self._ask,
            )
            self._q.put(("done", results, self._cancel.is_set()))
        except Exception as e:                       # should not happen: sheets are isolated
            self._q.put(("crash", f"{type(e).__name__}: {e}"))
