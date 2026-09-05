from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import time
from pathlib import Path
from typing import Awaitable, Callable

import httpx

from .agnes_client import AgnesClient, AgnesError
from .config import settings
from .creator_modes import animated_scene_indices
from .media_normalizer import normalize_clip

log = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int, int, bool], Awaitable[None]]


def _cache_root() -> Path:
    root = Path("data/clip_cache")
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for path in root.glob("*.mp4"):
        try:
            if now - path.stat().st_mtime > settings.creator_clip_cache_seconds:
                path.unlink(missing_ok=True)
        except OSError:
            pass
    return root


def _agnes_duration(seconds: float) -> int:
    # 5 and 10 seconds are supported by both common Agnes video generations.
    return 5 if seconds <= 6.5 else 10


def _motion_prompt(scene: dict) -> str:
    visual = str(scene.get("visual_prompt") or "").lower()
    if any(x in visual for x in ("face", "portrait", "وجه", "شخص")):
        profile = "Subtle natural blinking and breathing, minimal head movement, gentle camera push-in"
    elif any(x in visual for x in ("city", "landscape", "مدينة", "طبيعة")):
        profile = "Slow aerial reveal, atmospheric parallax, natural clouds and environmental movement"
    elif any(x in visual for x in ("product", "منتج")):
        profile = "Premium slow product orbit, controlled reflections, stable geometry"
    elif any(x in visual for x in ("run", "action", "اكشن", "يركض")):
        profile = "Dynamic tracking movement with controlled action and stable anatomy"
    else:
        profile = "Subtle cinematic parallax and motivated camera movement"
    base = str(scene.get("motion_prompt") or profile).strip()
    return (
        f"{base}. Natural subject motion and cinematic camera movement. Preserve the exact identity, face, clothing, "
        "anatomy, composition, palette and environment from the reference image. Stable details, no morphing, "
        "no new people, no text, no logo, no watermark, no sudden cuts."
    )[:4800]


class SceneAnimator:
    def __init__(self) -> None:
        self.client = AgnesClient()

    async def _submit(self, image: Path, prompt: str, seconds: float, end_image: Path | None = None) -> str:
        mode = "keyframes" if end_image else "i2v"
        data = {
            "prompt": prompt,
            "mode": mode,
            "duration": str(_agnes_duration(seconds)),
            "video_width": "768",
            "video_height": "1152",
            "video_size": "720P",
            "negative_prompt": "deformed face, unstable anatomy, flicker, morphing, text, logo, watermark, duplicate subject",
        }
        timeout = httpx.Timeout(90, connect=20, write=90, read=90)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as http:
            with image.open("rb") as first:
                files: dict[str, tuple[str, object, str]] = {
                    "reference_image": (image.name, first, "image/jpeg" if image.suffix.lower() in {".jpg", ".jpeg"} else "image/png")
                }
                if end_image:
                    with end_image.open("rb") as last:
                        files["end_frame_image"] = (end_image.name, last, "image/jpeg" if end_image.suffix.lower() in {".jpg", ".jpeg"} else "image/png")
                        response = await http.post(f"{settings.agnes_base_url}/api/tasks/simple", data=data, files=files)
                else:
                    response = await http.post(f"{settings.agnes_base_url}/api/tasks/simple", data=data, files=files)
        if response.status_code >= 400:
            raise AgnesError(f"Scene animation HTTP {response.status_code}: {response.text[:500]}")
        payload = response.json()
        task_id = str(payload.get("task_id") or "").strip()
        if not task_id:
            raise AgnesError(f"Scene animation did not return task_id: {payload}")
        return task_id

    async def animate(self, index: int, image: Path, scene: dict, seconds: float, output: Path, end_image: Path | None = None) -> Path:
        prompt = _motion_prompt(scene)
        digest = hashlib.sha256(image.read_bytes() + prompt.encode("utf-8") + str(_agnes_duration(seconds)).encode()).hexdigest()
        cached = _cache_root() / f"{digest}.mp4"
        if cached.is_file() and cached.stat().st_size > 1000:
            await asyncio.to_thread(shutil.copy2, cached, output)
            return output
        task_id = await self._submit(image, prompt, seconds, end_image)
        deadline = time.monotonic() + settings.creator_scene_animation_timeout
        last_status: dict | None = None
        while time.monotonic() < deadline:
            last_status = await self.client.status(task_id)
            state = last_status.get("status")
            if state == "completed":
                raw_output = output.with_name(output.stem + "_raw.mp4")
                await self.client.obtain_video(task_id, raw_output, last_status)
                if not raw_output.is_file() or raw_output.stat().st_size < 1000:
                    raise AgnesError("Animated scene video is empty")
                await normalize_clip(raw_output, output, seconds)
                raw_output.unlink(missing_ok=True)
                await asyncio.to_thread(shutil.copy2, output, cached)
                return output
            if state == "failed":
                raise AgnesError(str(last_status.get("error") or "Scene animation failed"))
            await asyncio.sleep(max(2, settings.agnes_poll_seconds))
        raise AgnesError(f"Scene animation timed out: {last_status}")


async def animate_creator_scenes(
    mode_key: str,
    images: list[Path],
    scenes: list[dict],
    durations: list[float],
    work: Path,
    progress: ProgressCallback | None = None,
) -> dict[int, Path]:
    selected = animated_scene_indices(mode_key, scenes)
    if not selected:
        return {}
    animator = SceneAnimator()
    semaphore = asyncio.Semaphore(max(1, settings.agnes_animation_concurrency))
    completed = 0
    lock = asyncio.Lock()

    async def one(index: int):
        nonlocal completed
        target = work / f"animated_scene_{index:02d}.mp4"
        transition = str(scenes[index].get("transition_style") or "").lower()
        end_image = None
        if mode_key == "cinematic" and index + 1 < len(images) and transition in {"continuous", "match_cut", "keyframes", "morph"}:
            end_image = images[index + 1]
        success = False
        try:
            async with semaphore:
                await animator.animate(index, images[index], scenes[index], durations[index], target, end_image)
            success = True
            return index, target
        except Exception as exc:
            log.warning("Animated scene %s failed; using cinematic still fallback: %s", index, exc)
            return index, None
        finally:
            async with lock:
                completed += 1
                if progress:
                    await progress(completed, len(selected), index, success)

    results = await asyncio.gather(*(one(index) for index in selected), return_exceptions=False)
    return {index: path for index, path in results if path is not None}
