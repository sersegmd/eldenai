from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import torch
import uvicorn
import whisper
from fastapi import FastAPI, File, HTTPException, UploadFile

MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
HOST = os.getenv("WHISPER_HOST", "127.0.0.1")
PORT = int(os.getenv("WHISPER_PORT", "8766"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI(title="ELDEN Whisper", docs_url=None, redoc_url=None)
_model = None
_model_lock = asyncio.Lock()


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(MODEL_NAME, device=DEVICE)
    return _model


@app.get("/health")
async def health():
    return {"ok": True, "model": MODEL_NAME, "device": DEVICE, "loaded": _model is not None}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = "", word_timestamps: bool = False):
    suffix = Path(file.filename or "voice.ogg").suffix or ".ogg"
    with tempfile.NamedTemporaryFile(prefix="elden_voice_", suffix=suffix, delete=False) as temp:
        path = Path(temp.name)
        while chunk := await file.read(512 * 1024):
            temp.write(chunk)
    try:
        if path.stat().st_size <= 0:
            raise HTTPException(status_code=400, detail="Empty audio file")
        async with _model_lock:
            model = await asyncio.to_thread(get_model)
            options = {"task": "transcribe", "fp16": DEVICE == "cuda", "verbose": False, "word_timestamps": word_timestamps}
            if language in {"ar", "fr", "en"}:
                options["language"] = language
            result = await asyncio.to_thread(model.transcribe, str(path), **options)
        text = str(result.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="No speech detected")
        segments = result.get("segments") or []
        logprobs = [float(s.get("avg_logprob", -1.0)) for s in segments if isinstance(s, dict)]
        no_speech = [float(s.get("no_speech_prob", 0.0)) for s in segments if isinstance(s, dict)]
        import math
        acoustic = math.exp(sum(logprobs) / len(logprobs)) if logprobs else 0.7
        speech = 1.0 - (sum(no_speech) / len(no_speech) if no_speech else 0.0)
        confidence = max(0.0, min(1.0, acoustic * speech))
        words = []
        if word_timestamps:
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                for item in segment.get("words") or []:
                    if isinstance(item, dict) and str(item.get("word") or "").strip():
                        words.append({
                            "word": str(item.get("word") or "").strip(),
                            "start": round(float(item.get("start", 0.0)), 3),
                            "end": round(float(item.get("end", 0.0)), 3),
                        })
        return {"ok": True, "text": text, "language": result.get("language") or language, "confidence": round(confidence, 3), "words": words}
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
