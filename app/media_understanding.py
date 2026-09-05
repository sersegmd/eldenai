from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .ai_client import describe_image


async def describe_video_bytes(data: bytes, duration: int, suffix: str = ".mp4") -> str:
    with tempfile.TemporaryDirectory(prefix="elden_context_") as folder:
        root = Path(folder)
        video = root / f"input{suffix}"
        frame = root / "frame.jpg"
        video.write_bytes(data)
        second = max(0, int(duration or 0) // 2)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-ss", str(second), "-i", str(video), "-frames:v", "1", "-q:v", "3", str(frame),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        if await process.wait() != 0 or not frame.is_file():
            return ""
        return await describe_image(frame.read_bytes(), "Describe this representative video frame for future conversational context.")
