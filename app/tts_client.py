from __future__ import annotations

import asyncio
import html
import re

import httpx

from .config import settings
from .runtime import tts_limiter
from .observability import event


class FishAudioError(RuntimeError):
    pass


# Only these two profiles are user-facing. Creator tones remain internal.
VOICE_LABELS = {
    "male": "👨 صوت ذكر",
    "female": "👩 صوت أنثى",
}
LANGUAGE_LABELS = {"auto": "🌐 تلقائي", "ar": "🇩🇿 الدارجة والعربية", "fr": "🇫🇷 الفرنسية", "en": "🇬🇧 الإنجليزية"}
_http_client: httpx.AsyncClient | None = None
_http_lock = asyncio.Lock()


def detect_speech_language(text: str) -> str:
    value = f" {text.lower()} "
    if re.search(r"[\u0600-\u06ff]", text) or any(x in value for x in (" rani ", " wach ", " saha ", " bzaf ", " ndir ")):
        return "ar"
    if re.search(r"[àâçéèêëîïôûùüÿœ]", value) or sum(x in value for x in (" le ", " la ", " une ", " avec ", " pour ", " vous ", " merci ")) >= 2:
        return "fr"
    return "en"


def voice_references() -> dict[str, str]:
    return {
        "male": settings.fish_voice_male or settings.fish_voice_deep,
        "female": settings.fish_voice_female or settings.fish_voice_soft_female,
        "news": settings.fish_voice_sports_calm,
        "documentary": settings.fish_voice_deep,
        "storyteller": settings.fish_voice_popular,
        "anime_storyteller": settings.fish_voice_youth,
    }


def resolve_reference(style: str, mode: str, text: str):
    lang = detect_speech_language(text) if mode not in {"ar", "fr", "en"} else mode
    tone = style if style in {"news", "documentary", "storyteller", "anime_storyteller"} else ""
    if tone:
        options = [
            (f"{tone}_{lang}", getattr(settings, f"fish_voice_{tone}_{lang}", "")),
            (tone, voice_references().get(tone, "")),
            (f"default_{lang}", getattr(settings, f"fish_voice_{lang}", "")),
        ]
    else:
        selected = style if style in VOICE_LABELS else "female"
        options = [
            (selected, voice_references().get(selected, "")),
            (f"default_{lang}", getattr(settings, f"fish_voice_{lang}", "")),
        ]
    options.append(("fallback", settings.fish_audio_reference_id))
    for profile, reference_id in options:
        if reference_id and not reference_id.startswith("PASTE_"):
            return reference_id, lang, profile
    raise FishAudioError("Selected voice is not configured")


def voice_configuration_status():
    return {"conversation": {key: bool(value) for key, value in (("male", voice_references()["male"]), ("female", voice_references()["female"]))}}


def clean_for_speech(text: str) -> str:
    value = re.sub(r"```[\s\S]*?```|`[^`]*`|<[^>]+>|https?://\S+", " ", html.unescape(text))
    value = re.sub(r"[*_#>|~]", " ", value)
    return " ".join(value.split())


def concise_voice_text(text: str, max_chars: int = 900) -> str:
    if len(text) <= max_chars:
        return text
    sentences = re.split(r"(?<=[.!?؟])\s+", text)
    selected: list[str] = []
    total = 0
    for sentence in sentences:
        if selected and total + len(sentence) + 1 > max_chars:
            break
        selected.append(sentence)
        total += len(sentence) + 1
    return " ".join(selected).strip()[:max_chars].rstrip() + "…"


async def _http() -> httpx.AsyncClient:
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        return _http_client
    async with _http_lock:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.fish_audio_timeout, connect=10),
                limits=httpx.Limits(max_connections=8, max_keepalive_connections=4, keepalive_expiry=60),
            )
    return _http_client


async def synthesize_speech(text, voice_style="female", language_mode="auto", *, operation_id=None, telegram_id=None):
    spoken = clean_for_speech(text)
    if voice_style in VOICE_LABELS:
        spoken = concise_voice_text(spoken)
    if not settings.fish_audio_api_key or not spoken:
        raise FishAudioError("Voice service is not configured")
    reference_id, lang, profile = resolve_reference(voice_style, language_mode, spoken)
    speed = {"male": 1.04, "female": 1.04, "news": 1.02, "documentary": .94, "storyteller": .98, "anime_storyteller": 1.06}.get(voice_style, 1.0)
    payload = {
        "text": spoken[:settings.fish_audio_max_chars],
        "reference_id": reference_id,
        "format": "mp3",
        "latency": settings.fish_audio_latency,
        "chunk_length": settings.fish_audio_chunk_length,
        "normalize": True,
        "prosody": {"speed": speed, "volume": 0, "normalize_loudness": True},
    }
    models = [settings.fish_audio_model] + ([settings.fish_audio_fallback_model] if settings.fish_audio_fallback_model != settings.fish_audio_model else [])
    async with tts_limiter.slot():
        await event("speech", "generation_started", f"{lang}:{profile}", operation_id=operation_id, telegram_id=telegram_id, metadata={"language": lang, "profile": profile})
        client = await _http()
        last_error = ""
        for model in models:
            try:
                response = await client.post(
                    f"{settings.fish_audio_base_url}/v1/tts",
                    headers={"Authorization": f"Bearer {settings.fish_audio_api_key}", "Content-Type": "application/json", "model": model},
                    json=payload,
                )
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue
            if response.status_code < 400 and len(response.content) > 100:
                await event("speech", "generation_completed", f"{lang}:{profile}", operation_id=operation_id, telegram_id=telegram_id)
                return response.content
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        raise FishAudioError(f"Voice generation failed: {last_error}")
