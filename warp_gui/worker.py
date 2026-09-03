"""Run a blocking callable on Qt's thread pool and report back via signals.

Keeps every warp-cli subprocess call off the GUI thread so the interface never
freezes while a command runs.
"""

from __future__ import annotations

import traceback

from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    finished = pyqtSignal(object)  # the callable's return value
    error = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - report everything to the UI
            traceback.print_exc()
            self.signals.error.emit(str(exc))
        else:
            self.signals.finished.emit(result)
