from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL

from .models import DownloadRequest, PlaylistEntry, PlaylistInfo

ProgressCallback = Callable[[dict[str, Any]], None]
LogCallback = Callable[[str], None]


class DownloadCancelled(Exception):
    pass


class YTDLPLogger:
    def __init__(self, callback: LogCallback | None = None) -> None:
        self.callback = callback

    def _emit(self, message: str) -> None:
        if self.callback and message.strip():
            self.callback(message.strip())

    def debug(self, message: str) -> None:
        # yt-dlp routes regular output through debug too.
        if not message.startswith("[debug]"):
            self._emit(message)

    def info(self, message: str) -> None:
        self._emit(message)

    def warning(self, message: str) -> None:
        self._emit(f"Avertissement : {message}")

    def error(self, message: str) -> None:
        self._emit(f"Erreur : {message}")


def _safe_duration(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def analyze_playlist(url: str) -> PlaylistInfo:
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": True,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Impossible d'analyser cette URL.")

    raw_entries = info.get("entries") or []
    entries: list[PlaylistEntry] = []
    for fallback_index, entry in enumerate(raw_entries, start=1):
        if not entry:
            continue
        index = entry.get("playlist_index") or fallback_index
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = fallback_index
        entries.append(
            PlaylistEntry(
                index=index,
                title=entry.get("title") or "Vidéo indisponible",
                duration=_safe_duration(entry.get("duration")),
                video_id=entry.get("id"),
            )
        )

    if not entries:
        raise RuntimeError("Aucune vidéo exploitable n'a été trouvée dans cette playlist.")

    return PlaylistInfo(
        title=info.get("title") or "Playlist YouTube",
        uploader=info.get("uploader") or info.get("channel"),
        entries=entries,
    )


def _video_format(output_format: str, quality: int | None) -> str:
    height = f"[height<={quality}]" if quality else ""
    if output_format == "webm":
        return (
            f"bv*{height}[ext=webm]+ba[ext=webm]/"
            f"b{height}[ext=webm]/b{height}/best"
        )
    return (
        f"bv*{height}[ext=mp4]+ba[ext=m4a]/"
        f"b{height}[ext=mp4]/b{height}/best"
    )


def build_ydl_options(
    request: DownloadRequest,
    progress_callback: ProgressCallback | None = None,
    log_callback: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    output_dir = Path(request.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    def progress_hook(data: dict[str, Any]) -> None:
        if cancel_event and cancel_event.is_set():
            raise DownloadCancelled("Téléchargement annulé.")
        if progress_callback:
            progress_callback(data)

    options: dict[str, Any] = {
        "outtmpl": str(
            output_dir
            / "%(playlist_title)s"
            / "%(playlist_index)03d - %(title).180B [%(id)s].%(ext)s"
        ),
        "download_archive": str(output_dir / ".yt-dlp-archive.txt"),
        "ignoreerrors": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "progress_hooks": [progress_hook],
        "logger": YTDLPLogger(log_callback),
        "noplaylist": False,
    }

    if request.playlist_items:
        options["playlist_items"] = request.playlist_items

    if request.output_format in {"mp3", "m4a"}:
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": request.output_format,
                "preferredquality": "192" if request.output_format == "mp3" else "0",
            }
        ]
    else:
        options["format"] = _video_format(request.output_format, request.quality)
        options["merge_output_format"] = request.output_format

    return options


def download_playlist(
    request: DownloadRequest,
    progress_callback: ProgressCallback | None = None,
    log_callback: LogCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    options = build_ydl_options(
        request,
        progress_callback=progress_callback,
        log_callback=log_callback,
        cancel_event=cancel_event,
    )
    with YoutubeDL(options) as ydl:
        result = ydl.download([request.url])
    if cancel_event and cancel_event.is_set():
        raise DownloadCancelled("Téléchargement annulé.")
    if result not in (None, 0):
        raise RuntimeError("yt-dlp a terminé avec une erreur.")
