# Optional Puter intelligence router

This integration is optional and never exposes the token to Telegram users.

1. Run `setup_puter_windows.bat` once.
2. Obtain a backend auth token from your Puter account.
3. Add to `.env`:

```env
PUTER_ENABLED=true
PUTER_AUTH_TOKEN=YOUR_PRIVATE_TOKEN
PUTER_MODE=fallback
PUTER_MODEL=gpt-5.4-nano
PUTER_PORT=8770
PUTER_BASE_URL=http://127.0.0.1:8770
```

Modes:
- `fallback`: local intelligence first, optional router only after a local failure.
- `advanced`: optional router first for deep, coding, research, creative and creator modes.
- `primary`: optional router first for all conversations.

Keep `PUTER_ENABLED=false` if the Node package or token is unavailable; the existing local intelligence continues normally.
