from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from .config import settings


@dataclass(frozen=True)
class CaptionWord:
    text: str
    start: float
    end: float


def _ass_time(seconds: float) -> str:
    value = max(0.0, seconds)
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    secs = int(value % 60)
    centis = int(round((value - int(value)) * 100))
    if centis >= 100:
        secs += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _clean_word(value: str) -> str:
    value = re.sub(r"[{}\\]", "", value)
    return " ".join(value.split())


def _groups(words: list[CaptionWord], max_words: int = 5, max_chars: int = 38) -> list[list[CaptionWord]]:
    result: list[list[CaptionWord]] = []
    current: list[CaptionWord] = []
    length = 0
    for word in words:
        clean = _clean_word(word.text)
        if not clean:
            continue
        normalized = CaptionWord(clean, max(0.0, word.start), max(word.start + 0.04, word.end))
        if current and (len(current) >= max_words or length + len(clean) + 1 > max_chars):
            result.append(current)
            current = []
            length = 0
        current.append(normalized)
        length += len(clean) + 1
    if current:
        result.append(current)
    return result


def _contains_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in text)


def build_ass(words: list[CaptionWord], output: Path, width: int = 720, height: int = 1280) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dynamic,{settings.caption_font_name.replace(",", " ")},52,{settings.caption_primary_color},{settings.caption_highlight_color},&H00101010,&H78000000,-1,0,0,0,100,100,0,0,3,4,0,2,70,70,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for group in _groups(words):
        start = group[0].start
        end = max(group[-1].end, start + 0.25)
        plain_text = " ".join(word.text for word in group).strip()
        parts: list[str] = []
        for word in group:
            centis = max(1, int(round((word.end - word.start) * 100)))
            parts.append(f"{{\\kf{centis}}}{word.text}")
        karaoke = " ".join(parts)
        if _contains_arabic(plain_text):
            text = "{\\fad(100,100)\\q2}" + "\u202b" + karaoke + "\u202c"
        else:
            text = "{\\fad(100,100)\\q2}" + karaoke
        events.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Dynamic,,0,0,0,,{text}"
        )
    output.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


async def _audio_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 30.0
    process = await asyncio.create_subprocess_exec(
        ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await process.communicate()
    try:
        return max(1.0, float(out.decode().strip()))
    except (TypeError, ValueError):
        return 30.0


async def audio_duration(path: Path) -> float:
    return await _audio_duration(path)


async def create_dynamic_captions(audio: Path, narration: str, language: str, output: Path) -> list[CaptionWord]:
    words: list[CaptionWord] = []
    try:
        from .voice_client import transcribe_with_timestamps
        transcript = await transcribe_with_timestamps(audio, "ar" if language == "dz" else language)
        words = [CaptionWord(item.text, item.start, item.end) for item in transcript.words if item.text.strip()]
    except Exception:
        words = []
    if not words:
        tokens = [token for token in narration.split() if token.strip()]
        duration = await _audio_duration(audio)
        step = duration / max(1, len(tokens))
        words = [CaptionWord(token, index * step, (index + 1) * step) for index, token in enumerate(tokens)]
    build_ass(words, output)
    return words
