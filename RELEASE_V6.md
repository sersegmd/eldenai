# ELDEN AI 6.0 — Reliability & Control Room

- Persistent media delivery queue with automatic retry and an independent upload fallback.
- Generation status separated from Telegram delivery status.
- Safe status-message editing for repeated/deleted messages.
- Global concurrency limits for creator, image, speech, music and uploads.
- Image moderation handling and safe symbolic fallback in Creator scenes.
- Automatic Arabic/Darija, French and English voice-ID routing; manual `/voicelang auto|ar|fr|en` override.
- High-quality speech model configured first with automatic fallback.
- Professional real-time admin control room for services, queues, operations, deliveries, errors and voice readiness.
- SQLite WAL, busy timeout and operation/event/delivery/context tables.
- Rotating logs and secret-safe HTTP logging.
- Creator/video/voice outputs are copied out of temporary folders before delivery, so failed uploads can be retried.
- Optional Puter.js Node intelligence router. It is disabled by default and never replaces the existing local route unless configured.

## Important
Copy new keys from `.env.example` into an existing `.env`. Run `setup_puter_windows.bat` only if the optional intelligence router is wanted.

## 6.0.1 single-delivery correction
- Atomically claims every pending delivery before upload.
- Uses one upload transport and one request per attempt.
- Ambiguous response timeouts are marked `uncertain` and are not automatically retried, preventing duplicate Reels.

## 6.0.2 hidden services
- Keeps only the main bot terminal visible by default.
- Runs local intelligence, video, voice understanding, and optional router without console windows.
- Saves each hidden service output in `logs/services/*.log`.
- Set `HIDE_SERVICE_WINDOWS=false` to restore separate service terminals for debugging.
