from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agnes_client import AgnesClient

VIDEO = b"\x00\x00\x00\x18ftypmp42" + (b"ELDEN" * 2048)


class Handler(BaseHTTPRequestHandler):
    local_video = ""
    video_attempts = 0

    def log_message(self, *_args):
        return

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/concurrency":
            return self._json({"ok": True})
        if self.path == "/api/tasks/task-local":
            return self._json({
                "task_id": "task-local", "status": "completed",
                "current_status": "completed", "current_progress": 1.0,
                "final_video_file": self.local_video,
            })
        if self.path == "/api/tasks/task-http":
            return self._json({
                "task_id": "task-http", "status": "completed",
                "current_status": "completed", "current_progress": 1.0,
                "final_video_file": "",
            })
        if self.path == "/api/video/task-http":
            type(self).video_attempts += 1
            if type(self).video_attempts == 1:
                return self._json({"detail": "Video not found yet"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(VIDEO)))
            self.end_headers()
            self.wfile.write(VIDEO)
            return
        self._json({"detail": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/api/tasks/simple":
            return self._json({"ok": True, "task_id": "task-http"})
        if self.path == "/api/tasks/task-http/stop":
            return self._json({"ok": True, "task_id": "task-http"})
        self._json({"detail": "not found"}, 404)


async def exercise(base_url: str, folder: Path, local_video: Path):
    client = AgnesClient(base_url=base_url)
    assert await client.health()
    task_id = await client.create("simple", "a cinematic city", 768, 1152, "en")
    assert task_id == "task-http"

    local_status = await client.status("task-local")
    assert local_status["status"] == "completed"
    local_copy = folder / "local-copy.mp4"
    local_size = await client.obtain_video("task-local", local_copy, local_status)
    assert local_size == len(VIDEO) and local_copy.read_bytes() == VIDEO

    http_status = await client.status("task-http")
    assert http_status["status"] == "completed"
    http_copy = folder / "http-copy.mp4"
    http_size = await client.obtain_video("task-http", http_copy, http_status)
    assert http_size == len(VIDEO) and http_copy.read_bytes() == VIDEO
    assert Handler.video_attempts == 2
    assert not (folder / "http-copy.mp4.part").exists()
    await client.stop("task-http")


def main():
    with tempfile.TemporaryDirectory(prefix="elden_agnes_test_") as temp:
        folder = Path(temp)
        local_video = folder / "source.mp4"
        local_video.write_bytes(VIDEO)
        Handler.local_video = str(local_video)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            asyncio.run(exercise(f"http://127.0.0.1:{server.server_port}", folder, local_video))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("Agnes client create/status/local-copy/HTTP-download/stop: PASS")


if __name__ == "__main__":
    main()
