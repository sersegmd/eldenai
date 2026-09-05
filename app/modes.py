from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import db
from .telegram_safe import safe_callback_answer

router = Router(name="ai-modes")

MODE_LABELS = {
    "quick": "⚡ Quick", "deep": "🧠 Deep Think", "research": "🔎 Research",
    "creative": "🎨 Creative", "coding": "💻 Coding", "study": "📚 Study",
    "business": "💼 Business", "creator": "🎬 Creator",
}

MODE_INSTRUCTIONS = {
    "quick": "Give fast, direct and concise answers.",
    "deep": "Reason carefully, examine assumptions, compare options and give a thorough answer.",
    "research": "Synthesize the supplied research sources, distinguish facts from uncertainty, and include source URLs when relevant.",
    "creative": "Prioritize originality, vivid ideas, alternatives and polished creative output.",
    "coding": "Act as a senior software engineer. Diagnose precisely, provide robust code and practical verification steps.",
    "study": "Teach step by step, use clear examples, check understanding and summarize key points.",
    "business": "Focus on customers, positioning, revenue, costs, risk, execution and measurable next steps.",
    "creator": "Optimize for social media: hooks, retention, storytelling, calls to action and platform-native formats.",
}


def mode_keyboard(selected: str = "quick") -> InlineKeyboardMarkup:
    rows = []
    pairs = list(MODE_LABELS.items())
    for i in range(0, len(pairs), 2):
        row = []
        for key, label in pairs[i:i+2]:
            row.append(InlineKeyboardButton(text=("✅ " if key == selected else "") + label, callback_data=f"aimode:{key}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("modes"))
@router.message(F.text.in_({"🧠 أوضاع الذكاء", "🧠 AI Modes", "🧠 Modes IA"}))
async def modes_page(message: Message):
    user = await db.get_user(message.from_user.id) or {}
    selected = user.get("ai_mode") or "quick"
    await message.answer(
        f"🎭 <b>أوضاع ELDEN AI</b>\n\nالوضع الحالي: <b>{MODE_LABELS.get(selected, MODE_LABELS['quick'])}</b>\nاختر طريقة معالجة طلباتك:",
        reply_markup=mode_keyboard(selected),
    )


@router.callback_query(F.data.startswith("aimode:"))
async def set_mode(callback: CallbackQuery):
    mode = callback.data.split(":", 1)[1]
    if mode not in MODE_LABELS:
        return await safe_callback_answer(callback, "اختيار غير صالح", show_alert=True)
    await db.update_user(callback.from_user.id, ai_mode=mode)
    await callback.message.edit_text(
        f"✅ تم اختيار <b>{MODE_LABELS[mode]}</b>.\nسيتم تطبيقه على الإجابات القادمة.",
        reply_markup=mode_keyboard(mode),
    )
    await safe_callback_answer(callback)
