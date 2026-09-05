from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import aiohttp

from .config import settings


class VoiceTranscriptionError(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceTranscript:
    text: str
    language: str
    confidence: float


@dataclass(frozen=True)
class TimedWord:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class TimedTranscript:
    text: str
    language: str
    words: tuple[TimedWord, ...]


async def transcribe_voice(path: Path, language: str = "") -> VoiceTranscript:
    timeout = aiohttp.ClientTimeout(total=settings.whisper_timeout, connect=10)
    form = aiohttp.FormData()
    form.add_field("file", path.read_bytes(), filename=path.name, content_type="audio/ogg")
    url = f"{settings.whisper_base_url}/transcribe"
    params = {"language": language} if language in {"ar", "fr", "en"} else None
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=form, params=params) as response:
                if response.status >= 400:
                    detail = (await response.text())[:500]
                    raise VoiceTranscriptionError(f"Whisper HTTP {response.status}: {detail}")
                data = await response.json()
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise VoiceTranscriptionError(f"Whisper service unavailable: {exc}") from exc
    text = str(data.get("text") or "").strip()
    if not text:
        raise VoiceTranscriptionError("Whisper did not detect speech")
    try:
        confidence = float(data.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7
    return VoiceTranscript(text[:12000], str(data.get("language") or language), max(0.0, min(1.0, confidence)))


async def transcribe_with_timestamps(path: Path, language: str = "") -> TimedTranscript:
    timeout = aiohttp.ClientTimeout(total=settings.whisper_timeout, connect=10)
    form = aiohttp.FormData()
    content_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/ogg"
    form.add_field("file", path.read_bytes(), filename=path.name, content_type=content_type)
    params = {"word_timestamps": "true"}
    if language in {"ar", "fr", "en"}:
        params["language"] = language
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{settings.whisper_base_url}/transcribe", data=form, params=params) as response:
                if response.status >= 400:
                    raise VoiceTranscriptionError(f"Caption alignment HTTP {response.status}")
                data = await response.json()
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise VoiceTranscriptionError(f"Caption alignment unavailable: {exc}") from exc
    words = []
    for item in data.get("words") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("word") or "").strip()
        if not text:
            continue
        try:
            start = float(item.get("start", 0.0)); end = float(item.get("end", start + 0.1))
        except (TypeError, ValueError):
            continue
        words.append(TimedWord(text, max(0.0, start), max(start + 0.04, end)))
    return TimedTranscript(str(data.get("text") or "").strip(), str(data.get("language") or language), tuple(words))
