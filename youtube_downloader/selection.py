from __future__ import annotations

import re

_ITEM_RE = re.compile(r"^\d+$")
_RANGE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")
_SLICE_RE = re.compile(r"^\d*:\d*(?::\d+)?$")


def normalize_custom_selection(value: str) -> str:
    """Normalize friendly playlist selection syntax to yt-dlp ITEM_SPEC syntax.

    Accepted examples:
      - 1,3,7
      - 10-15
      - 1,3,10-15
      - 5:20:2 (native yt-dlp slice syntax)
    """
    raw = value.strip()
    if not raw:
        raise ValueError("La sélection personnalisée est vide.")

    normalized: list[str] = []
    for token in (part.strip() for part in raw.split(",")):
        if not token:
            raise ValueError("La sélection contient un élément vide.")
        if _ITEM_RE.fullmatch(token) or _SLICE_RE.fullmatch(token):
            normalized.append(token)
            continue

        match = _RANGE_RE.fullmatch(token)
        if match:
            start, end = (int(match.group(1)), int(match.group(2)))
            if start < 1 or end < 1:
                raise ValueError("Les index commencent à 1.")
            if start > end:
                raise ValueError(f"Plage invalide : {token}.")
            normalized.append(f"{start}:{end}")
            continue

        raise ValueError(f"Sélection invalide : {token}.")

    return ",".join(normalized)


def build_range(start: int, end: int) -> str:
    if start < 1 or end < 1:
        raise ValueError("Les index commencent à 1.")
    if start > end:
        raise ValueError("Le début de la plage doit être inférieur ou égal à la fin.")
    return f"{start}:{end}"
