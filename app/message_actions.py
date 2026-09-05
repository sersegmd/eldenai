from __future__ import annotations

import html
import logging
import secrets
import time
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .ai_client import chat
from .telegram_safe import safe_callback_answer
from .tts_client import FishAudioError, synthesize_speech

log = logging.getLogger(__name__)
router = Router(name="message-actions")


@dataclass
class AnswerRecord:
    user_id: int
    prompt: str
    answer: str
    language: str
    mode: str
    personality: str
    context_note: str
    voice_style: str
    created_at: float


_records: dict[str, AnswerRecord] = {}


def _prune() -> None:
    now = time.time()
    for token, item in list(_records.items()):
        if now - item.created_at > 7200:
            _records.pop(token, None)
    while len(_records) > 500:
        _records.pop(next(iter(_records)), None)


def register_answer(user_id: int, prompt: str, answer: str, language: str, mode: str, personality: str, context_note: str, voice_style: str) -> str:
    _prune()
    token = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
    _records[token] = AnswerRecord(user_id, prompt[:12000], answer[:16000], language, mode, personality[:1200], context_note[:5000], voice_style, time.time())
    return token


def actions_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔊 قراءة بالصوت", callback_data=f"ans:voice:{token}"), InlineKeyboardButton(text="📝 إعادة الصياغة", callback_data=f"ans:rewrite:{token}")],
        [InlineKeyboardButton(text="🌍 ترجمة", callback_data=f"ans:translate:{token}"), InlineKeyboardButton(text="✂️ اختصار", callback_data=f"ans:short:{token}")],
        [InlineKeyboardButton(text="📚 شرح", callback_data=f"ans:explain:{token}"), InlineKeyboardButton(text="🔄 إعادة التوليد", callback_data=f"ans:regen:{token}")],
    ])


def translation_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇩🇿 الدارجة", callback_data=f"anstr:{token}:dz"), InlineKeyboardButton(text="العربية", callback_data=f"anstr:{token}:ar")],
        [InlineKeyboardButton(text="Français", callback_data=f"anstr:{token}:fr"), InlineKeyboardButton(text="English", callback_data=f"anstr:{token}:en")],
    ])


def get_record(token: str, user_id: int) -> AnswerRecord | None:
    item = _records.get(token)
    if not item or item.user_id != user_id or time.time() - item.created_at > 7200:
        return None
    return item


async def send_text_with_actions(message: Message, text: str, record: AnswerRecord) -> None:
    clean = text.replace("**", "").strip()
    parts = [clean[i:i+3900] for i in range(0, len(clean), 3900)] or ["…"]
    token = register_answer(record.user_id, record.prompt, clean, record.language, record.mode, record.personality, record.context_note, record.voice_style)
    for index, part in enumerate(parts):
        await message.answer(html.escape(part), parse_mode=ParseMode.HTML, reply_markup=actions_keyboard(token) if index == len(parts)-1 else None)


async def _transform(callback: CallbackQuery, record: AnswerRecord, instruction: str, regenerate: bool = False) -> None:
    await safe_callback_answer(callback)
    status = await callback.message.answer("⏳ جاري تجهيز الإجابة…")
    try:
        if regenerate:
            messages = [{"role": "user", "content": record.prompt}]
        else:
            messages = [{"role": "user", "content": f"{instruction}\n\nOriginal answer:\n{record.answer}"}]
        result = await chat(messages, record.personality, mode=record.mode, context_note=record.context_note)
        await status.delete()
        await send_text_with_actions(callback.message, result, record)
    except Exception:
        log.exception("Answer action failed")
        await status.edit_text("❌ تعذر تنفيذ الإجراء. حاول مجدداً.")


@router.callback_query(F.data.startswith("ans:"))
async def answer_action(callback: CallbackQuery):
    _, action, token = callback.data.split(":", 2)
    record = get_record(token, callback.from_user.id)
    if not record:
        return await safe_callback_answer(callback, "انتهت صلاحية هذه الإجابة.", show_alert=True)
    if action == "voice":
        await safe_callback_answer(callback)
        status = await callback.message.answer("🎙️ جاري إرسال رسالة صوتية…")
        try:
            await callback.message.bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VOICE)
            audio = await synthesize_speech(record.answer, record.voice_style)
            await callback.message.answer_voice(BufferedInputFile(audio, filename="ELDEN_answer.mp3"))
            await status.delete()
        except FishAudioError:
            await status.edit_text("❌ تعذر إرسال الرسالة الصوتية حالياً.")
        return
    if action == "translate":
        await safe_callback_answer(callback)
        return await callback.message.answer("🌍 اختر لغة الترجمة:", reply_markup=translation_keyboard(token))
    instructions = {
        "rewrite": "Rewrite this answer with a fresh, polished style while preserving its meaning.",
        "short": "Shorten this answer substantially while preserving all essential facts.",
        "explain": "Explain this answer more clearly with simple steps and examples where useful.",
    }
    if action == "regen":
        return await _transform(callback, record, "", regenerate=True)
    if action in instructions:
        return await _transform(callback, record, instructions[action])
    await safe_callback_answer(callback, "إجراء غير صالح", show_alert=True)


@router.callback_query(F.data.startswith("anstr:"))
async def translate_action(callback: CallbackQuery):
    _, token, language = callback.data.split(":", 2)
    record = get_record(token, callback.from_user.id)
    if not record:
        return await safe_callback_answer(callback, "انتهت صلاحية هذه الإجابة.", show_alert=True)
    names = {"dz": "Algerian Darija", "ar": "Arabic", "fr": "French", "en": "English"}
    if language not in names:
        return await safe_callback_answer(callback, "لغة غير صالحة", show_alert=True)
    await _transform(callback, record, f"Translate the answer into {names[language]}. Return only the translation.")


def clear_answer_records(user_id: int) -> None:
    for token, item in list(_records.items()):
        if item.user_id == user_id:
            _records.pop(token, None)
