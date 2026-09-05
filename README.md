# ELDEN AI 1.0

ELDEN AI is a production-oriented multilingual Telegram assistant for intelligent chat, smart web research, voice interaction, media understanding, AI video creation, subscriptions, and creator workflows.

## Highlights

- Algerian Darija, Arabic, French, and English.
- Smart research gate: searches only for explicit research, URLs, verification, or time-sensitive information.
- SearXNG primary search with DDGS fallback, caching, deduplication, and safe evidence handling.
- Resilient OpenRouter routing with reasoning, selective retries, and fallback models.
- Private semantic memory architecture with Qdrant and FastEmbed.
- Whisper voice understanding and optional Fish Audio replies.
- Agnes video and Creator workflows with progress, cancellation, checkpoints, dynamic captions, and duplicate-delivery protection.
- Telegram Stars subscriptions, quotas, referrals, coupons, and an authenticated control room.
- Prometheus metrics, optional Langfuse telemetry, and Guardrails validation.

## Windows requirements

Install Windows 10/11, Python 3.11 or 3.12, FFmpeg/FFprobe, Node.js 18+, and optionally Docker Desktop for private SearXNG search.

## Installation

```powershell
git clone https://github.com/sersegmd/eldenai.git
cd eldenai
setup_windows.bat
```

If `.env` was not created:

```powershell
copy .env.example .env
python setup.py
```

Configure at least:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_IDS=your_numeric_telegram_id
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openrouter/free
OPENROUTER_FALLBACK_MODELS=openrouter/free
DASHBOARD_PASSWORD=use_a_long_random_password
```

Start private search:

```powershell
docker compose up -d searxng
```

Start ELDEN AI:

```powershell
start_windows.bat
```

The control room is available at `http://127.0.0.1:8080` by default.

## Smart research

ELDEN AI does not search for greetings, bot capabilities, account information, transformations, or stable general knowledge. It searches for explicit research requests, current news, prices, weather, releases, live results, URLs, and fact verification. Results are deduplicated, cached, sanitized, and supplied with source URLs. If search is unavailable, the assistant continues without blocking.

## Reliability and privacy

Never commit `.env`, databases, logs, generated media, caches, or credentials. SQLite stores operational data. Semantic memory is isolated by Telegram user ID. OpenRouter retries transient failures only and can fall back when a model is unavailable. Generated videos use atomic delivery claims to prevent duplicate uploads.

## Validation

```powershell
python tests\test_smart_platform.py
python tests\test_advanced_features.py
python tests\test_creator_modes.py
python tests\test_image_client.py
python tests\test_agnes_client.py
python preflight.py
```

## Main commands

`/start`, `/menu`, `/help`, `/new`, `/modes`, `/voice`, `/video`, `/creator`, `/animate`, `/article`, `/image`, `/plans`, and `/privacy`.

## License and providers

Review the terms, privacy policies, quotas, and licenses of every connected provider before commercial deployment.