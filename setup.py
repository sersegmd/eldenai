from __future__ import annotations

import getpass
import secrets
from pathlib import Path

ENV_PATH = Path(__file__).with_name('.env')


def ask(prompt: str, default: str = '', secret: bool = False) -> str:
    suffix = f' [{default}]' if default else ''
    reader = getpass.getpass if secret else input
    value = reader(f'{prompt}{suffix}: ').strip()
    return value or default


def safe(value: str) -> str:
    return value.replace('\n', '').replace('\r', '')


def main() -> int:
    print('\n=== ELDEN AI secure setup ===')
    print('Values are saved locally in .env and are not included in the ZIP.\n')
    token = ask('Telegram BOT_TOKEN', secret=True)
    if ':' not in token:
        print('[ERROR] BOT_TOKEN does not look valid.')
        return 1
    openrouter_key = ask('OpenRouter API key', secret=True)
    fish_key = ask('Fish Audio API key for voice replies', secret=True)
    fish_voice = ask('Fish Audio voice/reference ID')
    fish_male = ask('Fish Audio voice/reference ID - male')
    fish_female = ask('Fish Audio voice/reference ID - female')
    admin_id = ask('Telegram admin ID', '8462511068')
    if not admin_id.isdigit():
        print('[ERROR] Telegram admin ID must contain digits only.')
        return 1
    dashboard_user = ask('Dashboard username', 'admin')
    dashboard_password = ask('Dashboard password (Enter to generate automatically)', secret=True) or secrets.token_urlsafe(18)
    phone_secret = secrets.token_urlsafe(32)
    content = f'''BOT_TOKEN={safe(token)}
ADMIN_TELEGRAM_IDS={safe(admin_id)}
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY={safe(openrouter_key)}
OPENROUTER_MODEL=thinkingmachines/inkling:free
OPENROUTER_TIMEOUT=240
OPENROUTER_SITE_URL=
AGNES_BASE_URL=http://127.0.0.1:8765
AGNES_AUTO_START=true
AGNES_START_COMMAND=npx free-short-video --no-open
AGNES_PROJECT_DIR=
AGNES_POLL_SECONDS=10
AGNES_TASK_TIMEOUT=3600
AGNES_DOWNLOAD_TIMEOUT=120
AGNES_DOWNLOAD_RETRIES=12
AGNES_STATUS_TIMEOUT=90
TELEGRAM_VIDEO_MAX_MB=49
TELEGRAM_RETRY_SECONDS=15
WHISPER_BASE_URL=http://127.0.0.1:8766
WHISPER_MODEL=small
WHISPER_TIMEOUT=600
MAX_VOICE_SECONDS=180
WHISPER_MIN_CONFIDENCE=0.55
FISH_AUDIO_BASE_URL=https://api.fish.audio
FISH_AUDIO_API_KEY={safe(fish_key)}
FISH_AUDIO_REFERENCE_ID={safe(fish_voice)}
FISH_VOICE_MALE={safe(fish_male)}
FISH_VOICE_FEMALE={safe(fish_female)}
FISH_AUDIO_MODEL=s2.1-pro-free
FISH_AUDIO_TIMEOUT=180
FISH_AUDIO_MAX_CHARS=3000
FISH_AUDIO_LATENCY=balanced
FISH_AUDIO_CHUNK_LENGTH=120
FREE_IMAGE_DAILY_LIMIT=20
PRO_IMAGE_DAILY_LIMIT=250
VIP_IMAGE_DAILY_LIMIT=1000
REFERRAL_INVITER_IMAGE_BONUS=5
REFERRAL_NEW_USER_IMAGE_BONUS=2
PRO_PRICE_STARS=500
VIP_PRICE_STARS=1000
PRO_DAILY_LIMIT=300
VIP_DAILY_LIMIT=2000
FREE_DAILY_LIMIT=100
FREE_VIDEO_DAILY_LIMIT=20
PRO_VIDEO_DAILY_LIMIT=60
VIP_VIDEO_DAILY_LIMIT=200
SUBSCRIPTION_DAYS=30
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8080
DASHBOARD_USER={safe(dashboard_user)}
DASHBOARD_PASSWORD={safe(dashboard_password)}
PHONE_HASH_SECRET={phone_secret}
SESSION_TTL_MINUTES=60
MAX_CONTEXT_MESSAGES=20
RATE_LIMIT_PER_MINUTE=8
DATABASE_PATH=elden_ai.db
LOG_LEVEL=INFO
'''
    ENV_PATH.write_text(content, encoding='utf-8')
    print('\n[OK] .env created successfully.')
    print(f'Dashboard username: {dashboard_user}')
    if not dashboard_password:
        print('A dashboard password was generated in .env.')
    print('You can now run start_windows.bat.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
