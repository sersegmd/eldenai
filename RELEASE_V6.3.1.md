# ELDEN AI 6.3.1 — Hugging Face Z-Image-Turbo

- Removed the previous image-generation provider and all of its configuration.
- Added Hugging Face `InferenceClient(provider="auto")`.
- Image model: `Tongyi-MAI/Z-Image-Turbo`.
- Fixed output size: 768×768 PNG.
- Standalone images and Creator scene images use the same new engine.
- Added token/model/provider/size/timeout settings and preflight diagnostics.
