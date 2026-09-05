from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from app.config import settings

ROOT = Path(__file__).resolve().parent
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def online(url: str) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=3) as response:
            json.loads(response.read().decode("utf-8", errors="replace"))
            return response.status == 200
    except Exception:
        return False


def service_dir() -> Path:
    path = ROOT / "logs" / "services"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _service_name(title: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in title).strip("_")


def _service_log(title: str):
    return (service_dir() / f"{_service_name(title)}.log").open("a", encoding="utf-8")


def start_cmd_console(title: str, command: str, cwd: Path) -> subprocess.Popen:
    name = _service_name(title)
    script = service_dir() / f"{name}.cmd"
    if settings.hide_service_windows:
        script.write_text(f'@echo off\ncd /d "{cwd}"\n{command}\n', encoding="utf-8")
        log_file = _service_log(title)
        return subprocess.Popen(
            ["cmd.exe", "/d", "/c", "call", str(script)],
            cwd=cwd,
            creationflags=CREATE_NO_WINDOW,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    script.write_text(f'@echo off\ntitle {title}\ncd /d "{cwd}"\n{command}\n', encoding="utf-8")
    return subprocess.Popen(["cmd.exe", "/d", "/k", "call", str(script)], cwd=cwd, creationflags=CREATE_NEW_CONSOLE)


def start_ollama_console() -> subprocess.Popen | None:
    standard = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    configured = os.getenv("OLLAMA_EXE", "").strip().strip('"')
    executable = Path(configured) if configured else standard
    if not executable.is_file():
        found = shutil.which("ollama.exe") or shutil.which("ollama")
        if found:
            executable = Path(found)
        else:
            print("[WARNING] Local intelligence service was not found. Set OLLAMA_EXE in .env.")
            return None
    if settings.hide_service_windows:
        log_file = _service_log("ELDEN - Intelligence")
        return subprocess.Popen(
            [str(executable), "serve"],
            cwd=ROOT,
            creationflags=CREATE_NO_WINDOW,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    script = service_dir() / "start_ollama.ps1"
    if executable == standard:
        launch_line = '& "$env:LOCALAPPDATA\\Programs\\Ollama\\ollama.exe" serve'
    else:
        escaped = str(executable).replace("'", "''")
        launch_line = f"& '{escaped}' serve"
    script.write_text(f'$Host.UI.RawUI.WindowTitle = "ELDEN - Intelligence"\n{launch_line}\n', encoding="utf-8")
    return subprocess.Popen([
        "powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", str(script)
    ], cwd=ROOT, creationflags=CREATE_NEW_CONSOLE)


def stop_tree(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def wait_for(name: str, url: str, seconds: int) -> None:
    print(f"[WAIT] Starting {name}...")
    deadline = time.time() + seconds
    while time.time() < deadline:
        if online(url):
            print(f"[OK] {name} is ready.")
            return
        time.sleep(2)
    print(f"[WARNING] {name} is unavailable; other features will continue.")


def main() -> int:
    (ROOT / "logs").mkdir(exist_ok=True)
    if settings.hide_service_windows:
        print("[MODE] Hidden services enabled. Only this ELDEN AI terminal will remain visible.")
        print(f"[LOGS] Hidden service logs: {service_dir()}")
    else:
        print("[MODE] Separate service terminals enabled.")
    services: list[subprocess.Popen] = []
    try:
        if settings.agnes_auto_start and not online(f"{settings.agnes_base_url}/api/concurrency"):
            command = settings.agnes_start_command
            configured_npx = os.getenv("NPX_EXE", "").strip().strip('"')
            npx_candidates = [
                configured_npx,
                shutil.which("npx.cmd") or shutil.which("npx") or "",
                str(Path(os.environ.get("APPDATA", "")) / "npm" / "npx.cmd"),
                str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "nodejs" / "npx.cmd"),
            ]
            npx = next((item for item in npx_candidates if item and Path(item).is_file()), "")
            if command.lower().startswith("npx ") and npx:
                command = f'"{npx}" {command[4:]}'
            cwd = Path(settings.agnes_project_dir) if settings.agnes_project_dir else ROOT
            services.append(start_cmd_console("ELDEN - Video", command, cwd))

        whisper_url = f"{settings.whisper_base_url}/health"
        if not online(whisper_url):
            python_exe = Path(os.getenv("WHISPER_PYTHON_EXE", "").strip().strip('"') or ROOT / ".venv-whisper" / "Scripts" / "python.exe")
            if not python_exe.is_file():
                raise RuntimeError("Voice Python environment is missing.")
            services.append(start_cmd_console("ELDEN - Voice Understanding", f'"{python_exe}" -u "{ROOT / "whisper_service.py"}"', ROOT))

        wait_for("voice understanding", whisper_url, 120)
        wait_for("video creation", f"{settings.agnes_base_url}/api/concurrency", 180)

        with (ROOT / "logs" / "runtime.log").open("a", encoding="utf-8") as log:
            bot_process = subprocess.Popen([sys.executable, "-u", "run.py"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
            assert bot_process.stdout is not None
            for line in bot_process.stdout:
                print(line, end="", flush=True); log.write(line); log.flush()
            return bot_process.wait()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"[ERROR] Startup could not continue: {exc}")
        return 1
    finally:
        for process in reversed(services):
            stop_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
