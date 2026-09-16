from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


OutputFormat = Literal["mp4", "webm", "mp3", "m4a"]


@dataclass(slots=True)
class DownloadRequest:
    url: str
    output_dir: Path
    playlist_items: str | None = None
    output_format: OutputFormat = "mp4"
    quality: int | None = None


@dataclass(slots=True)
class PlaylistEntry:
    index: int
    title: str
    duration: int | None = None
    video_id: str | None = None


@dataclass(slots=True)
class PlaylistInfo:
    title: str
    entries: list[PlaylistEntry]
    uploader: str | None = None
