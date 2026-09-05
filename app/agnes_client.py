from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import settings


class AgnesError(RuntimeError):
    """A readable error raised for Agnes API failures."""


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise AgnesError(f"Agnes returned invalid JSON: {raw[:200]!r}") from exc
    if not isinstance(value, dict):
        raise AgnesError("Agnes returned an unexpected response")
    return value


def _http_json(url: str, *, data: dict[str, Any] | None = None, timeout: int = 90) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json", "Connection": "close"}
    if data is not None:
        body = urllib.parse.urlencode({k: str(v) for k, v in data.items()}).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if data is not None else "GET")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return _decode_json(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read(600).decode("utf-8", errors="replace")
        raise AgnesError(f"Agnes HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise AgnesError(f"Agnes connection failed: {exc}") from exc


def _download_once(url: str, destination: Path, timeout: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"Accept": "video/mp4", "Connection": "close"})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            expected_text = response.headers.get("Content-Length") or ""
            expected = int(expected_text) if expected_text.isdigit() else 0
            written = 0
            with partial.open("wb") as output:
                while True:
                    chunk = response.read(512 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    written += len(chunk)
                    if expected and written >= expected:
                        break
            if written <= 0:
                raise AgnesError("Agnes returned an empty video")
            if expected and written < expected:
                raise AgnesError(f"Incomplete Agnes video: {written}/{expected} bytes")
            if "json" in content_type or "text/" in content_type:
                preview = partial.read_bytes()[:300].decode("utf-8", errors="replace")
                raise AgnesError(f"Agnes returned {content_type} instead of video: {preview}")
            os.replace(partial, destination)
            return written
    except urllib.error.HTTPError as exc:
        detail = exc.read(600).decode("utf-8", errors="replace")
        raise AgnesError(f"Agnes video HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise AgnesError(f"Agnes video connection failed: {exc}") from exc
    finally:
        if partial.exists() and not destination.exists():
            partial.unlink(missing_ok=True)


@dataclass
class AgnesClient:
    base_url: str = settings.agnes_base_url

    async def health(self) -> bool:
        try:
            result = await asyncio.to_thread(
                _http_json, f"{self.base_url}/api/concurrency", timeout=10
            )
            return bool(result.get("ok", True))
        except Exception:
            return False

    async def create(
        self,
        mode: str,
        text: str,
        width: int,
        height: int,
        lang: str,
        duration: int = 5,
        anchor_prompt: str = "",
        visual_style: str = "",
    ) -> str:
        endpoint = f"{self.base_url}/api/tasks/{mode}"
        voice = {
            "dz": "ar-DZ-AminaNeural",
            "ar": "ar-DZ-AminaNeural",
            "fr": "fr-FR-DeniseNeural",
            "en": "en-US-JennyNeural",
        }.get(lang, "en-US-JennyNeural")
        audio_lang = {"dz": "ar", "ar": "ar", "fr": "fr", "en": "en"}.get(lang, "en")
        common = {"video_width": width, "video_height": height, "execution_mode": "auto"}
        if mode == "simple":
            data = {**common, "prompt": text, "mode": "t2v", "duration": duration, "video_size": "720P"}
        elif mode == "creative":
            scene_count = max(1, math.ceil(duration / 10))
            base, extra = divmod(duration, scene_count)
            scene_durations = [base + (1 if i < extra else 0) for i in range(scene_count)]
            data = {
                **common, "idea": text, "style": visual_style or "cinematic, coherent, professional",
                "chaining_mode": "keyframes", "duration_source": "manual", "scene_count": scene_count,
                "uniform_duration": "false", "scene_durations_json": json.dumps(scene_durations),
                "audio_enabled": "true", "audio_voice": voice, "audio_lang": audio_lang,
                "subtitle_enabled": "true",
            }
        elif mode == "manuscript":
            data = {
                **common, "manuscript_text": text, "style": visual_style or "cinematic, professional",
                "video_duration": duration, "audio_enabled": "true", "audio_voice": voice,
                "audio_lang": audio_lang, "subtitle_enabled": "true",
            }
        elif mode == "poetry":
            scene_count = max(1, math.ceil(duration / 10))
            base, extra = divmod(duration, scene_count)
            scene_durations = [base + (1 if i < extra else 0) for i in range(scene_count)]
            data = {
                **common, "poem_text": text, "style": visual_style or "cinematic poetic atmosphere",
                "video_duration": duration, "duration_source": "manual", "scene_count": scene_count,
                "uniform_duration": "false", "scene_durations_json": json.dumps(scene_durations),
                "user_scene_prompts_json": "[]", "audio_enabled": "true",
                "audio_voice": voice, "audio_lang": audio_lang, "subtitle_enabled": "true",
            }
        elif mode == "anchor":
            data = {
                **common, "anchor_prompt": anchor_prompt, "script_text": text,
                "audio_source": "post_stitch", "audio_enabled": "true", "audio_voice": voice,
                "audio_lang": audio_lang, "subtitle_enabled": "true",
            }
        else:
            raise AgnesError(f"Unsupported Agnes mode: {mode}")
        result = await asyncio.to_thread(_http_json, endpoint, data=data, timeout=60)
        task_id = str(result.get("task_id") or "").strip()
        if not task_id:
            raise AgnesError(f"Agnes did not return task_id: {result}")
        return task_id

    async def status(self, task_id: str) -> dict[str, Any]:
        state = await asyncio.to_thread(
            _http_json,
            f"{self.base_url}/api/tasks/{task_id}",
            timeout=settings.agnes_status_timeout,
        )
        main_status = str(state.get("status") or "").lower().split(".")[-1]
        current_status = str(state.get("current_status") or "").lower().split(".")[-1]
        final_path = str(
            state.get("final_video_file")
            or state.get("final_video_path")
            or ""
        ).strip()
        completed = {"completed", "complete", "done", "success", "succeeded"}
        failed = {"failed", "error"}
        if final_path or main_status in completed or current_status in completed:
            detected = "completed"
        elif main_status in failed or current_status in failed:
            detected = "failed"
        elif main_status:
            detected = main_status
        else:
            detected = current_status or "running"
        raw_progress = state.get("current_progress", state.get("progress", 0)) or 0
        try:
            progress = float(raw_progress)
        except (TypeError, ValueError):
            progress = 0.0
        return {
            "status": detected,
            "progress": progress,
            "message": str(state.get("current_message") or state.get("current_step") or "Working"),
            "error": str(state.get("error") or state.get("error_message") or state.get("error_traceback") or "Unknown error"),
            "final_video_file": final_path,
            "dir_name": str(state.get("dir_name") or ""),
            "raw": state,
        }

    async def stop(self, task_id: str) -> None:
        await asyncio.to_thread(
            _http_json,
            f"{self.base_url}/api/tasks/{task_id}/stop",
            data={},
            timeout=30,
        )

    async def obtain_video(self, task_id: str, destination: Path, status: dict[str, Any] | None = None) -> int:
        """Copy the final file locally when possible, otherwise download with retries."""
        final_path = str((status or {}).get("final_video_file") or "").strip()
        if final_path:
            candidate = Path(final_path)
            if candidate.is_file() and candidate.stat().st_size > 0:
                await asyncio.to_thread(shutil.copy2, candidate, destination)
                return destination.stat().st_size

        url = f"{self.base_url}/api/video/{task_id}"
        last_error: Exception | None = None
        for attempt in range(1, settings.agnes_download_retries + 1):
            try:
                size = await asyncio.to_thread(
                    _download_once, url, destination, settings.agnes_download_timeout
                )
                if destination.is_file() and size > 0:
                    return size
            except Exception as exc:
                last_error = exc
                if attempt >= settings.agnes_download_retries:
                    break
                await asyncio.sleep(min(20, 2 + attempt * 2))
        raise AgnesError(
            f"Could not obtain completed video after {settings.agnes_download_retries} attempts: {last_error}"
        )
