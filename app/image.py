from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import db
from .ai_client import enhance_image_prompt
from .telegram_safe import safe_callback_answer

log = logging.getLogger(__name__)
router = Router(name="image-interface")
wizards: dict[int, dict] = {}


class InImageWizard(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in wizards)


def style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Realistic", callback_data="istyle:realistic"), InlineKeyboardButton(text="🎬 Cinematic", callback_data="istyle:cinematic")],
        [InlineKeyboardButton(text="🎨 Anime", callback_data="istyle:anime"), InlineKeyboardButton(text="🧊 3D", callback_data="istyle:3d")],
        [InlineKeyboardButton(text="🏷 Logo", callback_data="istyle:logo"), InlineKeyboardButton(text="📦 Product", callback_data="istyle:product")],
        [InlineKeyboardButton(text="✖ Cancel", callback_data="icancel")],
    ])


@router.message(Command("image"))
@router.message(F.text.in_({"🖼 إنشاء صورة", "🖼 Créer une image", "🖼 Create image"}))
async def image_command(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user.get("verified"):
        return await message.answer("🔐 استعمل /start أولاً.")
    wizards[message.from_user.id] = {"stage": "style", "lang": user.get("language", "dz")}
    await message.answer(
        "🖼 <b>ELDEN Image Studio</b>\n\nالواجهة جاهزة لتحضير طلب الصورة. محرك الصور الخارجي غير مربوط حالياً.",
        reply_markup=style_keyboard(),
    )


@router.callback_query(F.data.startswith("istyle:"))
async def choose_style(callback: CallbackQuery):
    state = wizards.get(callback.from_user.id)
    if not state:
        return await safe_callback_answer(callback, "ابدأ من /image", show_alert=True)
    style = callback.data.split(":", 1)[1]
    if style not in {"realistic", "cinematic", "anime", "3d", "logo", "product"}:
        return await safe_callback_answer(callback, "اختيار غير صالح", show_alert=True)
    state.update(style=style, stage="prompt")
    await callback.message.edit_text("✍️ أرسل وصف الصورة. سأجهز البرومبت فقط إلى أن يتم ربط API مناسب.")
    await safe_callback_answer(callback)


@router.callback_query(F.data == "icancel")
async def cancel_image(callback: CallbackQuery):
    wizards.pop(callback.from_user.id, None)
    await callback.message.edit_text("تم إلغاء واجهة إنشاء الصورة.")
    await safe_callback_answer(callback)


@router.message(Command("cancel"), InImageWizard())
async def cancel_image_command(message: Message):
    wizards.pop(message.from_user.id, None)
    await message.answer("تم إلغاء واجهة إنشاء الصورة.")


@router.message(InImageWizard(), F.text)
async def image_prompt(message: Message):
    state = wizards.get(message.from_user.id)
    if not state or state.get("stage") != "prompt":
        return
    prompt = message.text.strip()
    if len(prompt) < 3 or len(prompt) > 8000:
        return await message.answer("الوصف لازم يكون بين 3 و8000 حرف.")
    wizards.pop(message.from_user.id, None)
    try:
        prepared = await enhance_image_prompt(prompt, state["style"], "auto", state["lang"])
    except Exception:
        log.exception("Image prompt preparation failed")
        prepared = f"{prompt}, {state['style']} style, professional composition, high detail"
    await message.answer(
        "✅ <b>تم تجهيز طلب الصورة</b>\n\n"
        f"الستايل: <b>{html.escape(state['style'])}</b>\n"
        f"<blockquote>{html.escape(prepared[:3000])}</blockquote>\n"
        "ℹ️ إنشاء الصورة متوقف مؤقتاً لأن API الصور لم يتم اختياره بعد. لم تُستهلك أي حصة.",
    )


async def quick_image_from_voice(message: Message, prompt: str, lang: str, completion_voice: bool = False) -> None:
    wizards[message.from_user.id] = {"stage": "prompt", "lang": lang, "style": "cinematic"}
    await message.answer(
        "🖼 فهمت أنك تريد إنشاء صورة. واجهة الصور جاهزة لكن محرك API غير مربوط حالياً. "
        "أرسل الوصف كتابةً لتحضير البرومبت، أو استعمل /cancel."
    )
