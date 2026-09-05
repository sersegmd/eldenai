from __future__ import annotations

import asyncio
import html
import logging
import tempfile
import time
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import db
from .config import settings
from .context_memory import record_media
from .agnes_client import AgnesClient, AgnesError
from .telegram_safe import safe_callback_answer
from .ai_client import enhance_video_prompt
from .delivery import deliver_path

log = logging.getLogger(__name__)
router = Router(name="agnes-video")
wizards: dict[int, dict] = {}
monitor_tasks: set[asyncio.Task] = set()

VIDEO_TEXT = {
    "dz": {
        "title": "🎬 <b>ELDEN Video Studio</b>\nاختار نوع الفيديو:",
        "format": "📐 اختار مقاس الفيديو:",
        "duration": "⏱ اختار مدة الفيديو:",
        "content": "✍️ ابعث الفكرة أو النص لي حاب تحولو لفيديو.",
        "anchor": "🧑‍💼 ابعث وصف الشخصية/المقدم الرقمي.",
        "script": "🎙️ مليح. دُرك ابعث نص الكلام تاع المقدم.",
        "optimizing": "🧠 <b>ELDEN Prompt Engine</b> راهو يحلل فكرتك ويحضّر Prompt سينمائي مناسب لنوع ومقاس الفيديو…",
        "optimized": "✨ <b>تم تحسين البرومبت بنجاح</b>\n\n<blockquote>{prompt}</blockquote>\n\n🚀 بدأ إنشاء الفيديو بالإعدادات المحسنة.",
        "fallback": "⚠️ تعذر تحسين البرومبت مؤقتاً؛ راح نستعمل طلبك الأصلي باش ما نوقفوش العملية.",
        "queued": "✅ تسجل الطلب وبدأ إنشاء الفيديو…",
        "busy": "عندك فيديو راهو يتولد حالياً. استنى حتى يكمل أو ألغيه.",
        "limit": "وصلت لحصة الفيديو اليومية ({limit}). جرب غدوة أو رقّي الباقة.",
        "offline": "⚠️ خدمة الفيديو غير متاحة حالياً. حاول لاحقاً.",
        "failed": "❌ تعذر إنشاء الفيديو حالياً. حاول مجدداً بعد قليل.",
        "done": "✅ الفيديو واجد!",
        "cancelled": "تم إلغاء العملية.",
    },
    "ar": {},
    "fr": {
        "title": "🎬 <b>ELDEN Video Studio</b>\nChoisissez le type de vidéo :",
        "format": "📐 Choisissez le format :",
        "duration": "⏱ Choisissez la durée de la vidéo :",
        "content": "✍️ Envoyez l’idée ou le texte à transformer en vidéo.",
        "anchor": "🧑‍💼 Décrivez le présentateur numérique.",
        "script": "🎙️ Envoyez maintenant le script du présentateur.",
        "optimizing": "🧠 <b>ELDEN Prompt Engine</b> analyse votre idée et prépare un prompt cinématographique…",
        "optimized": "✨ <b>Prompt optimisé</b>\n\n<blockquote>{prompt}</blockquote>\n\n🚀 Création de la vidéo avec les paramètres optimisés.",
        "fallback": "⚠️ Optimisation indisponible; votre demande originale sera utilisée.",
        "queued": "✅ Demande enregistrée. Création en cours…",
        "busy": "Une vidéo est déjà en cours. Attendez ou annulez-la.",
        "limit": "Quota vidéo quotidien atteint ({limit}).",
        "offline": "⚠️ Le service vidéo est temporairement indisponible.",
        "failed": "❌ Impossible de créer la vidéo maintenant. Réessayez plus tard.",
        "done": "✅ Votre vidéo est prête !",
        "cancelled": "Opération annulée.",
    },
    "en": {
        "title": "🎬 <b>ELDEN Video Studio</b>\nChoose a video type:",
        "format": "📐 Choose the video format:",
        "duration": "⏱ Choose the video duration:",
        "content": "✍️ Send the idea or text to turn into a video.",
        "anchor": "🧑‍💼 Describe the digital presenter.",
        "script": "🎙️ Now send the presenter's script.",
        "optimizing": "🧠 <b>ELDEN Prompt Engine</b> is analyzing your idea and building a production-ready cinematic prompt…",
        "optimized": "✨ <b>Prompt optimized</b>\n\n<blockquote>{prompt}</blockquote>\n\n🚀 Video creation started with optimized settings.",
        "fallback": "⚠️ Prompt optimization is temporarily unavailable; the original request will be used.",
        "queued": "✅ Request accepted. Video creation started…",
        "busy": "You already have a video running. Wait or cancel it.",
        "limit": "Daily video quota reached ({limit}).",
        "offline": "⚠️ The video service is temporarily unavailable.",
        "failed": "❌ Could not create the video now. Please try again later.",
        "done": "✅ Your video is ready!",
        "cancelled": "Operation cancelled.",
    },
}
VIDEO_TEXT["ar"] = {**VIDEO_TEXT["dz"], **{
    "title": "🎬 <b>ELDEN Video Studio</b>\nاختر نوع الفيديو:",
    "format": "📐 اختر أبعاد الفيديو:",
    "duration": "⏱ اختر مدة الفيديو:",
    "content": "✍️ أرسل الفكرة أو النص الذي تريد تحويله إلى فيديو.",
    "anchor": "🧑‍💼 أرسل وصف المقدم الرقمي.",
    "script": "🎙️ أرسل الآن نص كلام المقدم.",
}}

def vt(lang: str, key: str, **values) -> str:
    table = VIDEO_TEXT.get(lang, VIDEO_TEXT["dz"])
    return table.get(key, VIDEO_TEXT["dz"].get(key, key)).format(**values)


def mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Simple", callback_data="vtype:simple"), InlineKeyboardButton(text="🎞 Creative", callback_data="vtype:creative")],
        [InlineKeyboardButton(text="📄 Manuscript", callback_data="vtype:manuscript"), InlineKeyboardButton(text="📜 Poetry", callback_data="vtype:poetry")],
        [InlineKeyboardButton(text="🧑‍💼 Digital Anchor", callback_data="vtype:anchor")],
        [InlineKeyboardButton(text="✖ Cancel", callback_data="vcancel:wizard")],
    ])


def format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 9:16", callback_data="vfmt:768:1152"), InlineKeyboardButton(text="🖥 16:9", callback_data="vfmt:1152:768")],
        [InlineKeyboardButton(text="◻ 1:1", callback_data="vfmt:1024:1024")],
        [InlineKeyboardButton(text="‹ Back", callback_data="vback:modes"), InlineKeyboardButton(text="✖ Cancel", callback_data="vcancel:wizard")],
    ])


def duration_keyboard(mode: str) -> InlineKeyboardMarkup:
    values = (5, 10, 15, 20)
    rows = []
    for i in range(0, len(values), 3):
        rows.append([InlineKeyboardButton(text=f"{n} sec", callback_data=f"vdur:{n}") for n in values[i:i+3]])
    rows.append([InlineKeyboardButton(text="✖ Cancel", callback_data="vcancel:wizard")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Cancel video", callback_data=f"vstop:{task_id}")]
    ])


class InVideoWizard(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in wizards)


client = AgnesClient()


def _track(coro) -> None:
    task = asyncio.create_task(coro)
    monitor_tasks.add(task)
    task.add_done_callback(monitor_tasks.discard)


async def safe_edit_message(bot_instance: Bot, chat_id: int, message_id: int | None, text: str, reply_markup=None) -> None:
    if not message_id:
        return
    try:
        await bot_instance.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        if "message is not modified" not in str(exc).lower():
            log.warning("Could not edit Telegram status message: %s", exc)


@router.message(F.text.in_({"🎬 إنشاء فيديو", "🎬 Créer une vidéo", "🎬 Create video"}))
@router.message(Command("video"))
async def video_command(message: Message):
    user = await db.get_user(message.from_user.id)
    lang = (user or {}).get("language", "dz")
    if not user or not user.get("verified"):
        return await message.answer("🔐 Complete /start verification first.")
    if await db.get_active_video_job(message.from_user.id):
        return await message.answer(vt(lang, "busy"))
    if not await client.health():
        return await message.answer(vt(lang, "offline", url=settings.agnes_base_url))
    wizards[message.from_user.id] = {"stage": "mode", "lang": lang}
    await message.answer(vt(lang, "title"), reply_markup=mode_keyboard())


@router.callback_query(F.data.startswith("vtype:"))
async def choose_type(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in wizards:
        return await safe_callback_answer(callback, "Start with /video", show_alert=True)
    mode = callback.data.split(":", 1)[1]
    if mode not in {"simple", "creative", "manuscript", "poetry", "anchor"}:
        return await safe_callback_answer(callback, "Invalid", show_alert=True)
    wizards[uid].update(mode=mode, stage="format")
    await callback.message.edit_text(vt(wizards[uid]["lang"], "format"), reply_markup=format_keyboard())
    await safe_callback_answer(callback, )


@router.callback_query(F.data.startswith("vfmt:"))
async def choose_format(callback: CallbackQuery):
    uid = callback.from_user.id
    state = wizards.get(uid)
    if not state:
        return await safe_callback_answer(callback, "Start with /video", show_alert=True)
    try:
        _, width, height = callback.data.split(":")
        width, height = int(width), int(height)
    except Exception:
        return await safe_callback_answer(callback, "Invalid", show_alert=True)
    if (width, height) not in {(768,1152),(1152,768),(1024,1024)}:
        return await safe_callback_answer(callback, "Invalid", show_alert=True)
    if state["mode"] == "anchor":
        state.update(width=width, height=height, stage="anchor_prompt", duration=20)
        await callback.message.edit_text(vt(state["lang"], "anchor"))
    else:
        state.update(width=width, height=height, stage="duration")
        await callback.message.edit_text(vt(state["lang"], "duration"), reply_markup=duration_keyboard(state["mode"]))
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("vdur:"))
async def choose_duration(callback: CallbackQuery):
    state = wizards.get(callback.from_user.id)
    if not state or state.get("stage") != "duration":
        return await safe_callback_answer(callback, "Start with /video", show_alert=True)
    try:
        duration = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await safe_callback_answer(callback, "Invalid duration", show_alert=True)
    allowed = {5, 10, 15, 20}
    if duration not in allowed:
        return await safe_callback_answer(callback, "Invalid duration", show_alert=True)
    state.update(duration=duration, stage="content")
    await callback.message.edit_text(vt(state["lang"], "content"))
    await safe_callback_answer(callback)


@router.callback_query(F.data == "vback:modes")
async def back_modes(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid in wizards:
        wizards[uid] = {"stage":"mode", "lang":wizards[uid]["lang"]}
        await callback.message.edit_text(vt(wizards[uid]["lang"], "title"), reply_markup=mode_keyboard())
    await safe_callback_answer(callback, )


@router.callback_query(F.data == "vcancel:wizard")
async def cancel_wizard(callback: CallbackQuery):
    state = wizards.pop(callback.from_user.id, None)
    await callback.message.edit_text(vt((state or {}).get("lang","dz"), "cancelled"))
    await safe_callback_answer(callback, )


@router.message(Command("cancel"), InVideoWizard())
async def cancel_wizard_command(message: Message):
    state = wizards.pop(message.from_user.id, None) or {}
    await message.answer(vt(state.get("lang","dz"), "cancelled"))


@router.message(InVideoWizard(), F.text)
async def wizard_text(message: Message):
    uid = message.from_user.id
    state = wizards.get(uid)
    if not state:
        return
    text = message.text.strip()
    if state["stage"] == "anchor_prompt":
        state.update(anchor_prompt=text[:3000], stage="content")
        return await message.answer(vt(state["lang"], "script"))
    if state["stage"] != "content":
        return
    if len(text) < 3:
        return await message.answer("Text is too short.")
    if state["mode"] == "anchor" and len(text) > 500:
        return await message.answer("نص المقدم طويل. الحد الأقصى يقارب 20 ثانية (500 حرف).")
    if len(text) > 50000:
        return await message.answer("Text is too long (max 50,000 characters).")
    if await db.get_active_video_job(uid):
        wizards.pop(uid, None)
        return await message.answer(vt(state["lang"], "busy"))
    if uid in settings.admin_ids:
        allowed, limit = True, 999999
    else:
        allowed, _, limit = await db.reserve_video_quota(uid)
    if not allowed:
        wizards.pop(uid, None)
        return await message.answer(vt(state["lang"], "limit", limit=limit))

    status_message = await message.answer(vt(state["lang"], "optimizing"))
    optimized = ""
    target_for_llm = state.get("anchor_prompt", "") if state["mode"] == "anchor" else text
    try:
        optimized = await enhance_video_prompt(
            target_for_llm, state["mode"], state["width"], state["height"], state["lang"]
        )
        if optimized:
            await safe_edit_message(message.bot, uid, status_message.message_id, vt(state["lang"], "optimized", prompt=html.escape(optimized)))
    except Exception:
        log.exception("Video prompt enhancement failed; using safe fallback")
        await safe_edit_message(message.bot, uid, status_message.message_id, vt(state["lang"], "fallback"))

    submit_text = optimized if optimized and state["mode"] in {"simple", "creative"} else text
    anchor_prompt = optimized if optimized and state["mode"] == "anchor" else state.get("anchor_prompt", "")
    visual_style = optimized if optimized and state["mode"] in {"manuscript", "poetry"} else ""
    try:
        task_id = await client.create(
            state["mode"], submit_text, state["width"], state["height"], state["lang"],
            duration=state.get("duration", 5), anchor_prompt=anchor_prompt, visual_style=visual_style,
        )
        await db.create_video_job(uid, task_id, state["mode"], status_message.message_id)
        record_media(uid, "video", text, "generated")
    except Exception as exc:
        if uid not in settings.admin_ids:
            await db.refund_video_quota(uid)
        log.exception("Could not create Agnes task")
        await safe_edit_message(message.bot, uid, status_message.message_id, vt(state["lang"], "failed", error=html.escape(str(exc)[:500])))
        wizards.pop(uid, None)
        return
    wizards.pop(uid, None)
    await safe_edit_message(message.bot, uid, status_message.message_id, vt(state["lang"], "queued", task=task_id), reply_markup=task_keyboard(task_id))
    _track(monitor_video(message.bot, uid, task_id, status_message.message_id, state["lang"]))


async def quick_video_from_voice(message: Message, prompt: str, lang: str) -> None:
    """Generate the professional voice-command default: Simple, 9:16, 10 seconds."""
    uid = message.from_user.id
    if not await client.health():
        await message.answer(vt(lang, "offline", url=settings.agnes_base_url))
        return
    wizards[uid] = {
        "stage": "content",
        "lang": lang,
        "mode": "simple",
        "width": 768,
        "height": 1152,
        "duration": 10,
    }
    synthetic = message.model_copy(update={"text": prompt})
    await wizard_text(synthetic)


async def voice_video_status(message: Message, lang: str) -> None:
    job = await db.get_active_video_job(message.from_user.id)
    if not job:
        await message.answer("ℹ️ ما عندك حتى فيديو قيد الإنشاء.")
        return
    await message.answer(
        f"🎬 <b>حالة الفيديو</b>\nالحالة: <code>{html.escape(str(job['status']))}</code>\n"
        f"التقدم: <b>{int(job.get('progress') or 0)}%</b>\n<code>{job['task_id']}</code>"
    )


async def voice_cancel_video(message: Message, lang: str) -> None:
    job = await db.get_active_video_job(message.from_user.id)
    if not job:
        await message.answer("ℹ️ ما عندك حتى فيديو قيد الإنشاء.")
        return
    try:
        await client.stop(job["task_id"])
    except Exception as exc:
        log.warning("Voice cancel could not stop Agnes task %s: %s", job["task_id"], exc)
    await db.update_video_job(job["task_id"], status="cancelled", progress=0, completed=True)
    await message.answer("🛑 تم إلغاء الفيديو.")


@router.callback_query(F.data.startswith("vstop:"))
async def stop_video(callback: CallbackQuery):
    task_id = callback.data.split(":",1)[1]
    job = await db.get_video_job(task_id)
    if not job or (job["telegram_id"] != callback.from_user.id and callback.from_user.id not in settings.admin_ids):
        return await safe_callback_answer(callback, "Not allowed", show_alert=True)
    try:
        await client.stop(task_id)
        await db.update_video_job(task_id, status="cancelled", progress=0)
        await callback.message.edit_text("🛑 Video generation cancelled.")
    except Exception as exc:
        await safe_callback_answer(callback, str(exc)[:180], show_alert=True)
        return
    await safe_callback_answer(callback, )


async def _compress_if_needed(source: Path) -> Path:
    max_bytes = settings.telegram_video_max_mb * 1024 * 1024
    if not source.is_file() or source.stat().st_size <= 0:
        raise RuntimeError("Downloaded video is missing or empty")
    if source.stat().st_size <= max_bytes:
        return source
    target = source.with_name(source.stem + "_telegram.mp4")
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(source),
            "-vf", "scale=1280:-2:force_original_aspect_ratio=decrease",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "31",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(target),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        code = await process.wait()
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required for videos larger than the Telegram limit") from exc
    if code != 0 or not target.is_file() or target.stat().st_size <= 0:
        raise RuntimeError("FFmpeg could not prepare the video for Telegram")
    if target.stat().st_size > max_bytes:
        raise RuntimeError(
            f"Video is still larger than {settings.telegram_video_max_mb} MB after compression"
        )
    return target


async def _send_video_with_retry(bot_instance: Bot, telegram_id: int, path: Path, caption: str):
    result=await deliver_path(bot_instance,telegram_id,"video",path,path.name,caption)
    if not result.success: log.warning("Video saved for automatic redelivery: %s",result.delivery_id)
    return result


async def monitor_video(
    bot_instance: Bot,
    telegram_id: int,
    task_id: str,
    message_id: int | None,
    lang: str,
):
    started = time.monotonic()
    last_percent = -1
    status_failures = 0
    try:
        while time.monotonic() - started < settings.agnes_task_timeout:
            await asyncio.sleep(settings.agnes_poll_seconds)
            try:
                info = await client.status(task_id)
                status_failures = 0
            except AgnesError as exc:
                status_failures += 1
                log.warning("Agnes status attempt %s failed for %s: %s", status_failures, task_id, exc)
                if status_failures in {1, 5, 10}:
                    await safe_edit_message(
                        bot_instance,
                        telegram_id,
                        message_id,
                        "⏳ <b>خدمة الفيديو مشغولة مؤقتاً</b>\nنعاود المحاولة تلقائياً…",
                        reply_markup=task_keyboard(task_id),
                    )
                await asyncio.sleep(min(30, status_failures * 3))
                continue

            progress = info["progress"]
            if progress <= 1:
                progress *= 100
            percent = max(0, min(100, int(progress)))
            status = info["status"]
            await db.update_video_job(task_id, status=status, progress=percent)

            if status in {"failed", "error"}:
                raise RuntimeError(info["error"][:700])
            if status in {"cancelled", "stopped"}:
                await db.update_video_job(task_id, status="cancelled", completed=True)
                return

            if percent != last_percent:
                blocks = "█" * (percent // 10) + "░" * (10 - percent // 10)
                await safe_edit_message(
                    bot_instance,
                    telegram_id,
                    message_id,
                    f"🎬 <b>{percent}%</b> <code>{blocks}</code>\n"
                    "جاري تجهيز المشاهد بجودة عالية…",
                    reply_markup=task_keyboard(task_id),
                )
                last_percent = percent

            if status == "completed":
                await safe_edit_message(
                    bot_instance,
                    telegram_id,
                    message_id,
                    f"✅ <b>الفيديو واجد</b>\n"
                    "⬇️ جاري استلام الملف النهائي…",
                )
                with tempfile.TemporaryDirectory(prefix="elden_video_") as folder:
                    output = Path(folder) / f"ELDEN_{task_id}.mp4"
                    size_bytes = await client.obtain_video(task_id, output, info)
                    if not output.is_file() or size_bytes <= 0:
                        raise RuntimeError("Agnes returned no usable video file")
                    size_mb = size_bytes / (1024 * 1024)
                    await safe_edit_message(
                        bot_instance,
                        telegram_id,
                        message_id,
                        f"✅ <b>تم استلام الفيديو</b>\n"
                        f"📦 الحجم: <b>{size_mb:.1f} MB</b>\n"
                        "⚙️ جاري تجهيزه للإرسال…",
                    )
                    prepared = await _compress_if_needed(output)
                    await safe_edit_message(
                        bot_instance,
                        telegram_id,
                        message_id,
                        "📤 <b>جاري إرسال الفيديو…</b>",
                    )
                    await _send_video_with_retry(
                        bot_instance,
                        telegram_id,
                        prepared,
                        vt(lang, "done"),
                    )

                await db.update_video_job(
                    task_id, status="completed", progress=100, error="", completed=True
                )
                if message_id:
                    try:
                        await bot_instance.delete_message(telegram_id, message_id)
                    except Exception:
                        pass
                return

        raise RuntimeError("Video task exceeded the configured monitoring timeout")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.exception("Video monitor failed: %s", task_id)
        await db.update_video_job(
            task_id, status="failed", error=str(exc)[:900], completed=True
        )
        await safe_edit_message(
            bot_instance,
            telegram_id,
            message_id,
            vt(lang, "failed", error=html.escape(str(exc)[:500])),
        )
        if not message_id:
            try:
                await bot_instance.send_message(
                    telegram_id, vt(lang, "failed", error=html.escape(str(exc)[:500]))
                )
            except Exception:
                pass


async def restore_video_monitors(bot_instance: Bot):
    for job in await db.list_active_video_jobs():
        user = await db.get_user(job["telegram_id"])
        _track(
            monitor_video(
                bot_instance,
                job["telegram_id"],
                job["task_id"],
                job.get("status_message_id"),
                (user or {}).get("language", "dz"),
            )
        )
