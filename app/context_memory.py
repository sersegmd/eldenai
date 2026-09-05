from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class MediaItem:
    kind: str
    prompt: str
    source: str
    file_id: str = ""
    created_at: float = 0.0


_items: dict[int, deque[MediaItem]] = defaultdict(lambda: deque(maxlen=10))


def record_media(user_id: int, kind: str, prompt: str, source: str = "generated", file_id: str = "") -> None:
    _items[user_id].append(MediaItem(kind, prompt[:6000].strip(), source, file_id, time.time()))


def latest_media(user_id: int, kind: str | None = None) -> MediaItem | None:
    for item in reversed(_items.get(user_id, ())):
        if kind is None or item.kind == kind:
            return item
    return None


def context_summary(user_id: int) -> str:
    rows = list(_items.get(user_id, ()))
    if not rows:
        return ""
    lines = ["Recent session media context:"]
    for item in rows[-6:]:
        lines.append(f"- {item.kind} ({item.source}): {item.prompt[:700]}")
    return "\n".join(lines)


def resolve_media_followup(user_id: int, text: str) -> tuple[str, str] | None:
    value = " ".join(text.lower().split())
    references = (
        "اجعلها", "خليها", "بدلها", "غيرها", "نفسها", "الصورة السابقة", "الفيديو السابق",
        "make it", "change it", "same image", "same video", "rends-la", "modifie-la", "la même",
    )
    if not any(marker in value for marker in references):
        return None
    preferred = "video" if "فيديو" in value or "video" in value or "vidéo" in value else "image"
    item = latest_media(user_id, preferred) or latest_media(user_id)
    if not item:
        return None
    combined = f"Previous {item.kind} request: {item.prompt}\nRequested modification: {text}"
    return item.kind, combined


def clear_context(user_id: int) -> None:
    _items.pop(user_id, None)
