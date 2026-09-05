# ELDEN AI 6.1

- Full-quality 1024x1536 scene generation; no image quality reduction.
- Creates all scene prompts first.
- Generates speech and scene images concurrently.
- Generates a consistency anchor first, then remaining images in parallel batches.
- Per-scene retry and moderation-safe fallback; successful scenes are never regenerated.
- Stable scene ordering after parallel completion.
- One final FFmpeg assembly after every image is ready.
- 30-minute model-list cache, reusable requests sessions, and one-hour image-result cache.
- Automatic hardware encoder detection with reliable CPU fallback.
- Optional licensed soundtrack folder, loudness normalization and voice ducking.
- Stage timing events visible in the control room.
- No new user request queue was added.
