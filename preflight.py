from __future__ import annotations

import json
import socket
import sys
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from app.config import settings


def dashboard_port_is_free() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((settings.dashboard_host, settings.dashboard_port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def agnes_is_reachable() -> bool:
    request = urllib.request.Request(
        f"{settings.agnes_base_url}/api/concurrency",
        headers={"Accept": "application/json", "Connection": "close"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
            return response.status == 200 and bool(data.get("ok", True))
    except Exception:
        return False


def main() -> int:
    print("[PRECHECK] Configuration: OK")
    if not settings.openrouter_api_key or settings.openrouter_api_key.startswith("PASTE_"):
        print("[ERROR] OPENROUTER_API_KEY is missing."); return 6
    print(f"[PRECHECK] Language model: {settings.openrouter_model}")
    if not dashboard_port_is_free():
        print(
            f"[ERROR] Dashboard port {settings.dashboard_port} is already in use.\n"
            "Close the older ELDEN AI window, or change DASHBOARD_PORT in .env."
        )
        return 2
    print(f"[PRECHECK] Dashboard port {settings.dashboard_port}: available")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("[ERROR] FFmpeg/FFprobe was not found. Creator and media validation are disabled.")
        return 4
    print("[PRECHECK] FFmpeg and FFprobe: available")
    free = shutil.disk_usage(Path.cwd()).free
    if free < 5 * 1024**3:
        print(f"[WARNING] Low free disk space: {free / 1024**3:.1f} GB")
    else:
        print(f"[PRECHECK] Free disk: {free / 1024**3:.1f} GB")
    test_dir=Path("data");test_dir.mkdir(exist_ok=True);probe=test_dir/".write_test"
    try: probe.write_text("ok");probe.unlink();print("[PRECHECK] Data directory: writable")
    except OSError as exc: print(f"[ERROR] Data directory is not writable: {exc}");return 5
    if settings.caption_font_file:
        if Path(settings.caption_font_file).is_file(): print("[PRECHECK] Custom caption font: available")
        else: print("[WARNING] CAPTION_FONT_FILE does not exist; CAPTION_FONT_NAME fallback will be used.")
    try:
        from app.creator_checkpoint import stale
        pending=len(stale())
        if pending: print(f"[RECOVERY] {pending} incomplete Creator checkpoint(s) detected.")
    except Exception as exc: print(f"[WARNING] Checkpoint scan failed: {exc}")
    if settings.agnes_auto_start and not shutil.which("npx"):
        print("[ERROR] Node.js/npx was not found. Install Node.js 18+ to launch Agnes.")
        return 3
    if settings.agnes_auto_start:
        print("[PRECHECK] Node.js npx: available")
    print("[PRECHECK] Image Studio: interface-only (backend intentionally disabled)")
    if agnes_is_reachable():
        print(f"[PRECHECK] Agnes {settings.agnes_base_url}: online")
    else:
        print(
            f"[WARNING] Agnes {settings.agnes_base_url} is offline. "
            "Chat will work, but /video requires Agnes to be running."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
