from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from .downloader import DownloadCancelled, analyze_playlist, download_playlist
from .models import DownloadRequest


class AnalyzerWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    @Slot()
    def run(self) -> None:
        try:
            info = analyze_playlist(self.url)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(info)


class DownloadWorker(QObject):
    progress = Signal(object)
    log = Signal(str)
    finished = Signal()
    cancelled = Signal()
    error = Signal(str)

    def __init__(self, request: DownloadRequest) -> None:
        super().__init__()
        self.request = request
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            download_playlist(
                self.request,
                progress_callback=self._on_progress,
                log_callback=self.log.emit,
                cancel_event=self._cancel_event,
            )
        except DownloadCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            if self._cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))
            return
        self.finished.emit()

    def _on_progress(self, data: dict[str, Any]) -> None:
        self.progress.emit(data)
