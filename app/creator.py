from __future__ import annotations

import asyncio
import hashlib
import json
import time
import html
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import db
from .ai_client import generate_creator_plan
from .config import settings
from .captioning import audio_duration, create_dynamic_captions
from .context_memory import record_media
from .image_client import ImageBackendClient, ImageModerationBlocked
from .telegram_safe import safe_callback_answer, safe_edit_text, safe_delete_message
from .tts_client import synthesize_speech
from .delivery import deliver_path
from .observability import event, stage
from .creator_modes import MODES, get_mode
from .scene_animator import animate_creator_scenes
from .creator_templates import enrich_idea
from .creator_checkpoint import save as save_checkpoint, complete as complete_checkpoint
from .creator_extras import create_thumbnail, publishing_pack
from .creator_eta import estimate_seconds, label as eta_label

log = logging.getLogger(__name__)
router = Router(name="content-creator")
wizards: dict[int, dict] = {}
running: set[int] = set()
tasks: set[asyncio.Task] = set()
image_client = ImageBackendClient()

VOICE_TONE_LABELS = {
    "news": "📰 إخباري",
    "documentary": "🎥 وثائقي",
    "storyteller": "📖 راوي قصص",
    "anime_storyteller": "🎌 راوي قصص أنمي",
}

VOICE_STYLE_FOR_TONE = {
    "news": "news",
    "documentary": "documentary",
    "storyteller": "storyteller",
    "anime_storyteller": "anime_storyteller",
}


def choose_voice_tone(idea: str, suggested: str = "") -> str:
    value = idea.lower()
    if any(word in value for word in ("انمي", "أنمي", "anime", "manga", "مانغا")):
        return "anime_storyteller"
    if any(word in value for word in ("اخبار", "أخبار", "اخباري", "إخباري", "نشرة", "news", "bulletin", "journal télévisé")):
        return "news"
    if any(word in value for word in ("وثائقي", "وثايقي", "documentary", "documentaire")):
        return "documentary"
    if any(word in value for word in ("قصة", "قصه", "حكاية", "رواية", "story", "tale", "histoire")):
        return "storyteller"
    return suggested if suggested in VOICE_TONE_LABELS else "documentary"


class InCreatorWizard(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.from_user and message.from_user.id in wizards)


def platform_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Reel", callback_data="creator:reel"), InlineKeyboardButton(text="📱 TikTok", callback_data="creator:tiktok")],
        [InlineKeyboardButton(text="📸 Instagram Reel", callback_data="creator:instagram"), InlineKeyboardButton(text="▶️ YouTube Short", callback_data="creator:youtube")],
        [InlineKeyboardButton(text="✖ إلغاء", callback_data="creator:cancel")],
    ])


def creator_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MODES["fast"].label, callback_data="creator_mode:fast")],
        [InlineKeyboardButton(text=MODES["balanced"].label, callback_data="creator_mode:balanced")],
        [InlineKeyboardButton(text=MODES["cinematic"].label, callback_data="creator_mode:cinematic")],
        [InlineKeyboardButton(text="✖ إلغاء", callback_data="creator:cancel")],
    ])


def duration_from_text(text: str) -> int:
    match = re.search(r"(\d{1,3})\s*(?:ثاني|ثوان|second|sec|seconde)", text.lower())
    duration = int(match.group(1)) if match else 30
    return max(10, min(settings.creator_max_duration, duration))


def is_creator_request(text: str) -> bool:
    value = text.lower()
    format_word = any(x in value for x in ("reel", "ريل", "tiktok", "تيك توك", "youtube short", "يوتيوب شورت", "instagram reel"))
    request_word = any(x in value for x in ("انش", "أنش", "ديرلي", "صايبلي", "اعمل", "create", "make", "generate", "crée"))
    return format_word and request_word


def _status(done: int, current: int = -1) -> str:
    labels = [
        "🧠 كتابة السكريبت وتحليل النوع",
        "🎙️ اختيار النبرة وإنشاء الصوت",
        "🖼️ إنشاء المشاهد الاحترافية",
        "📝 مزامنة الكتابة الديناميكية",
        "🎞️ تجهيز الانتقالات السينمائية",
        "🎵 معالجة الصوت والموسيقى",
        "✂️ اللمسات الأخيرة",
    ]
    rows = ["🎬 <b>AI Content Creator</b>", ""]
    for index, label in enumerate(labels):
        mark = "✅" if index < done else "⏳" if index == current else "▫️"
        rows.append(f"{label}... {mark}")
    return "\n".join(rows)


async def _run(*args: str) -> None:
    process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, error = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(error.decode("utf-8", errors="replace")[-900:])


def _subtitle_filter_path(path: Path) -> str:
    value = path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    result = f"subtitles=filename='{value}'"
    custom = Path(settings.caption_font_file) if settings.caption_font_file else None
    if custom and custom.is_file():
        fonts_dir = custom.resolve().parent.as_posix().replace(":", r"\:").replace("'", r"\'")
        result += f":fontsdir='{fonts_dir}'"
    return result


def _normalized_scene_durations(scenes: list[dict], total_duration: float) -> list[float]:
    raw: list[float] = []
    for scene in scenes:
        try:
            seconds = float(scene.get("seconds") or 0)
        except (TypeError, ValueError):
            seconds = 0.0
        raw.append(max(1.0, seconds))
    if not raw:
        raise RuntimeError("Creator plan has no timed scenes")
    scale = max(1.0, total_duration) / sum(raw)
    durations = [max(0.5, value * scale) for value in raw]
    correction = max(0.5, total_duration - sum(durations[:-1]))
    durations[-1] = correction
    return durations


async def delete_creator_folder_later(folder: Path, delay: int = 3600) -> None:
    await asyncio.sleep(delay)
    for attempt in range(10):
        try:
            if folder.exists():
                await asyncio.to_thread(shutil.rmtree, folder)
            return
        except PermissionError:
            if attempt < 9:
                await asyncio.sleep(15)
            else:
                log.warning("Creator folder stayed locked: %s", folder)
        except FileNotFoundError:
            return
        except Exception as exc:
            log.warning("Creator cleanup failed for %s: %s", folder, exc)
            return


_ENCODER_CACHE: tuple[str, list[str]] | None = None

def _video_encoder(ffmpeg: str) -> tuple[str, list[str]]:
    global _ENCODER_CACHE
    if _ENCODER_CACHE is not None:
        return _ENCODER_CACHE
    configured = settings.creator_video_encoder
    candidates = [configured] if configured != "auto" else ["h264_nvenc", "h264_qsv", "h264_amf"]
    for encoder in candidates:
        if encoder not in {"h264_nvenc", "h264_qsv", "h264_amf"}:
            continue
        probe = subprocess.run(
            [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1", "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if probe.returncode == 0:
            args = {
                "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"],
                "h264_qsv": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "23"],
                "h264_amf": ["-c:v", "h264_amf", "-quality", "speed", "-qp_i", "23", "-qp_p", "23"],
            }[encoder]
            _ENCODER_CACHE = (encoder, args)
            return _ENCODER_CACHE
    _ENCODER_CACHE = ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"])
    return _ENCODER_CACHE


def _licensed_music(voice_tone: str) -> Path | None:
    root = Path(settings.creator_music_dir)
    if not root.is_absolute(): root = Path.cwd() / root
    if not root.is_dir(): return None
    supported = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg"}
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in supported)
    preferred = [path for path in files if voice_tone in path.stem.lower()]
    return (preferred or files)[0] if files else None


async def _assemble(
    images: list[Path],
    scene_durations: list[float],
    voice: Path,
    captions: Path,
    output: Path,
    voice_tone: str = "documentary",
    animated_clips: dict[int, Path] | None = None,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is not available")
    if not images or len(images) != len(scene_durations):
        raise RuntimeError("Creator scenes and durations do not match")
    animated_clips = animated_clips or {}
    work = output.parent
    total_duration = sum(scene_durations)
    encoder_name, encoder_args = _video_encoder(ffmpeg)
    log.info("Creator encoder selected: %s", encoder_name)
    command = [ffmpeg, "-y"]
    for index, (image, seconds) in enumerate(zip(images, scene_durations)):
        clip = animated_clips.get(index)
        if clip and clip.is_file():
            command.extend(["-stream_loop", "-1", "-t", f"{seconds:.3f}", "-i", str(clip)])
        else:
            command.extend(["-loop", "1", "-framerate", "30", "-t", f"{seconds:.3f}", "-i", str(image)])
    filters=[];labels=[]
    for index, seconds in enumerate(scene_durations):
        transition=min(0.45,max(0.18,seconds/8));fade_out=max(0.0,seconds-transition);label=f"v{index}"
        common=f"scale=900:1280:force_original_aspect_ratio=increase,crop=900:1280,"
        if index in animated_clips:
            visual=common+"scale=720:1280,setsar=1,fps=30,settb=AVTB,"
        else:
            zoom_speed=0.00055+(index%3)*0.00012
            visual=common+f"zoompan=z='min(zoom+{zoom_speed:.5f},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=720x1280:fps=30,setsar=1,settb=AVTB,"
        filters.append(f"[{index}:v]{visual}trim=duration={seconds:.3f},setpts=PTS-STARTPTS,eq=contrast=1.025:saturation=1.06,fade=t=in:st=0:d={transition:.3f},fade=t=out:st={fade_out:.3f}:d={transition:.3f},format=yuv420p[{label}]")
        labels.append(f"[{label}]")
    filters.append("".join(labels)+f"concat=n={len(images)}:v=1:a=0[outv]")
    silent=work/"visual_story.mp4"
    command.extend(["-filter_complex",";".join(filters),"-map","[outv]","-an","-t",f"{total_duration:.3f}",*encoder_args,"-r","30","-pix_fmt","yuv420p","-movflags","+faststart",str(silent)])
    await _run(*command)
    music=work/"music.m4a";fade_start=max(0.0,total_duration-2);licensed=_licensed_music(voice_tone)
    if licensed:
        await _run(ffmpeg,"-y","-stream_loop","-1","-i",str(licensed),"-t",f"{total_duration:.3f}","-af",f"loudnorm=I=-22:LRA=9:TP=-2,afade=t=in:st=0:d=2,afade=t=out:st={fade_start:.3f}:d=2","-c:a","aac","-b:a","160k",str(music))
    else:
        music_filter=(f"[0:a]volume=0.025[a0];[1:a]volume=0.018[a1];[a0][a1]amix=inputs=2:duration=longest,afade=t=in:st=0:d=2,afade=t=out:st={fade_start:.3f}:d=2[a]")
        await _run(ffmpeg,"-y","-f","lavfi","-i",f"sine=frequency=174:duration={total_duration:.3f}","-f","lavfi","-i",f"sine=frequency=261.6:duration={total_duration:.3f}","-filter_complex",music_filter,"-map","[a]","-c:a","aac",str(music))
    mixed=work/"mixed.mp4"
    # Split narration before using it as both side-chain control and final mix input.
    audio_filter=(f"[1:a]volume=1.0,asplit=2[voice_sidechain][voice_mix];[2:a]volume={settings.creator_music_volume}[music];[music][voice_sidechain]sidechaincompress=threshold=0.035:ratio=6:attack=20:release=500[ducked_music];[voice_mix][ducked_music]amix=inputs=2:duration=longest:normalize=0[a]")
    await _run(ffmpeg,"-y","-i",str(silent),"-i",str(voice),"-i",str(music),"-filter_complex",audio_filter,"-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k","-t",f"{total_duration:.3f}","-movflags","+faststart",str(mixed))
    await _run(ffmpeg,"-y","-i",str(mixed),"-vf",_subtitle_filter_path(captions),*encoder_args,"-c:a","copy","-movflags","+faststart",str(output))
    if not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError("Final video was not created")


def _creator_cache_root() -> Path:
    root = Path("data/image_cache")
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in root.glob("*"):
        try:
            if now - old.stat().st_mtime > 3600: old.unlink(missing_ok=True)
        except OSError: pass
    return root


async def _generate_scene(
    index: int,
    prompt: str,
    narration_segment: str,
    work: Path,
    semaphore: asyncio.Semaphore,
    progress_callback,
) -> tuple[int, Path]:
    key = hashlib.sha256((prompt + "|768x768").encode("utf-8")).hexdigest()
    cache_data = _creator_cache_root() / f"{key}.img"
    cache_meta = _creator_cache_root() / f"{key}.json"
    if cache_data.is_file() and cache_meta.is_file() and time.time() - cache_data.stat().st_mtime < 3600:
        meta = json.loads(cache_meta.read_text(encoding="utf-8"))
        ext = ".jpg" if "jpeg" in meta.get("content_type", "") else ".png"
        path = work / f"scene_{index:02d}{ext}"
        await asyncio.to_thread(shutil.copy2, cache_data, path)
        await progress_callback(index)
        return index, path
    async with semaphore:
        try:
            generated = await image_client.generate(prompt, "768x768")
        except ImageModerationBlocked:
            safe_prompt = f"Premium family-friendly non-graphic symbolic cinematic scene representing: {narration_segment}. No violence, blood, injury, nudity, disturbing imagery, text, logos or watermarks. Square 1:1, centered subject, crop-safe for vertical 9:16 reels, 768x768."
            generated = await image_client.generate(safe_prompt, "768x768")
        except Exception:
            fallback = f"Professional cinematic visual metaphor for: {narration_segment}. Dramatic lighting, premium composition, family-friendly, no text, square 1:1, centered and crop-safe for vertical reels, 768x768."
            generated = await image_client.generate(fallback, "768x768")
    ext = ".jpg" if "jpeg" in generated.content_type else ".png"
    path = work / f"scene_{index:02d}{ext}"
    path.write_bytes(generated.data)
    cache_data.write_bytes(generated.data)
    cache_meta.write_text(json.dumps({"content_type": generated.content_type}), encoding="utf-8")
    await progress_callback(index)
    return index, path


async def run_creator(message: Message, idea: str, platform: str, lang: str, creator_mode: str = "balanced") -> None:
    uid = message.from_user.id
    if uid in running:
        await message.answer("⏳ عندك محتوى كامل قيد الإنشاء.")
        return
    if not image_client.configured:
        await message.answer("🖼️ صانع المحتوى الكامل متوقف مؤقتاً لأن محرك الصور غير مربوط. يمكنك استعمال /video للفيديو المباشر أو /image لتحضير برومبت صورة.")
        return
    allowed = True if uid in settings.admin_ids else (await db.reserve_video_quota(uid))[0]
    if not allowed:
        await message.answer("وصلت لحصة الفيديو اليومية.")
        return
    running.add(uid)
    requested_duration = duration_from_text(idea)
    job_id = await db.create_creator_job(uid, platform, requested_duration)
    operation_id = await db.create_operation(uid, "creator", lang)
    status = await message.answer(_status(0, 0))
    creator_folder: Path | None = None
    quota_committed = False
    started = time.perf_counter()
    timings: dict[str, float] = {}
    try:
        mark=time.perf_counter(); await stage(operation_id,"creator","planning",5,"كتابة السكريبت",telegram_id=uid)
        template_key, enriched_idea = enrich_idea(idea)
        plan = await generate_creator_plan(enriched_idea, requested_duration, platform, lang); timings["planning"]=time.perf_counter()-mark
        await save_checkpoint(job_id,"plan",user_id=uid,template=template_key,mode=creator_mode,idea=idea,plan=plan)
        creator_mode = get_mode(creator_mode).key
        mode_info = get_mode(creator_mode)
        eta_text = eta_label(estimate_seconds(creator_mode, len(plan.get("scenes") or [])))
        await safe_edit_text(status, _status(1,1) + f"\n\nالوضع: <b>{mode_info.label}</b> · الوقت المتوقع: <b>{eta_text}</b>")
        voice_tone = choose_voice_tone(idea, plan.get("voice_tone", "")); user=await db.get_user(uid) or {}
        scenes=list(plan["scenes"][:settings.creator_max_scenes])
        if not scenes: raise RuntimeError("Creator plan has no scenes")
        creator_folder=Path(tempfile.mkdtemp(prefix="elden_creator_")); work=creator_folder
        visual_style=str(plan.get("visual_style") or "Premium cinematic visual storytelling")
        bible=str(plan.get("character_bible") or "Keep recurring characters and environments consistent")
        prompts=[]
        for index,scene in enumerate(scenes):
            segment=str(scene.get("narration_segment") or "").strip(); direction=str(scene.get("visual_prompt") or segment or idea)
            prompts.append(f"{visual_style}. CONSISTENCY BIBLE: {bible}. Scene {index+1}/{len(scenes)}. Narration: {segment}. Visual direction: {direction}. Premium production quality with coherent recurring subjects. Same recurring faces, clothing, objects, palette and environment continuity. Premium cinematic composition, professional lighting, realistic depth and textures, sharp subject, square 1:1, centered crop-safe composition, full 768x768 quality, no captions, logos, watermark or accidental text.")
        await safe_edit_text(status,_status(1,1)+f"\n\nالنبرة: <b>{VOICE_TONE_LABELS[voice_tone]}</b>\n🖼️ سيتم إنشاء {len(scenes)} مشاهد على دفعات متزامنة.")
        voice_mark=time.perf_counter(); images_mark=time.perf_counter(); quota_committed=True
        voice_task=asyncio.create_task(synthesize_speech(plan["narration"],VOICE_STYLE_FOR_TONE[voice_tone],user.get("voice_language_mode") or "auto",operation_id=operation_id,telegram_id=uid))
        completed=0; lock=asyncio.Lock(); semaphore=asyncio.Semaphore(max(1,settings.creator_image_parallelism))
        async def progress(_index):
            nonlocal completed
            async with lock:
                completed+=1
                await safe_edit_text(status,_status(2,2)+f"\n\nتم إنشاء الصور: <b>{completed}/{len(scenes)}</b>\n⚡ إنشاء متزامن بجودة كاملة")
                await stage(operation_id,"creator","parallel_images",20+round(45*completed/len(scenes)),f"{completed}/{len(scenes)}",telegram_id=uid)
        # Generate the visual anchor first while speech runs, then generate all remaining scenes concurrently.
        first_task=asyncio.create_task(_generate_scene(0,prompts[0],str(scenes[0].get("narration_segment") or idea),work,semaphore,progress))
        first=await first_task
        rest_tasks=[asyncio.create_task(_generate_scene(i,prompts[i],str(scenes[i].get("narration_segment") or idea),work,semaphore,progress)) for i in range(1,len(scenes))]
        rest=await asyncio.gather(*rest_tasks,return_exceptions=True)
        voice_data=await voice_task; timings["voice"]=time.perf_counter()-voice_mark; timings["images"]=time.perf_counter()-images_mark
        results=[first,*rest]
        errors=[item for item in results if isinstance(item,Exception)]
        if errors: raise RuntimeError(f"{len(errors)} scene images failed: {errors[0]}")
        images=[path for _,path in sorted(results,key=lambda item:item[0])]
        await save_checkpoint(job_id,"images",user_id=uid,images=[str(path) for path in images],mode=creator_mode)
        voice_path=work/"voice.mp3";voice_path.write_bytes(voice_data);final_duration=await audio_duration(voice_path);scene_durations=_normalized_scene_durations(scenes,final_duration)
        cap_mark=time.perf_counter();captions=work/"dynamic_captions.ass"
        captions_task=asyncio.create_task(create_dynamic_captions(voice_path,plan["narration"],lang,captions))
        animation_mark=time.perf_counter()
        await safe_edit_text(status,_status(3,3)+f"\n\nالوضع: <b>{mode_info.label}</b>")
        async def animation_progress(done,total,index,success):
            await safe_edit_text(status,_status(3,3)+f"\n\nالوضع: <b>{mode_info.label}</b>\nتم تحريك المشاهد: <b>{done}/{total}</b>")
            await stage(operation_id,"creator","scene_animation",65+round(12*done/max(1,total)),f"{done}/{total}",telegram_id=uid)
        animated_clips=await animate_creator_scenes(creator_mode,images,scenes,scene_durations,work,animation_progress)
        timings["animation"]=time.perf_counter()-animation_mark
        await save_checkpoint(job_id,"animation",user_id=uid,clips={str(k):str(v) for k,v in animated_clips.items()},mode=creator_mode)
        await captions_task;timings["captions"]=time.perf_counter()-cap_mark
        render_mark=time.perf_counter();await safe_edit_text(status,_status(4,4));output=work/"ELDEN_Creator.mp4";await _assemble(images,scene_durations,voice_path,captions,output,voice_tone,animated_clips);timings["render"]=time.perf_counter()-render_mark
        await safe_edit_text(status,_status(7)+"\n\n📤 جاري إرسال الفيديو النهائي…")
        await save_checkpoint(job_id,"rendered",user_id=uid,output=str(output),mode=creator_mode)
        delivery=await deliver_path(message.bot,message.chat.id,"video",output,"ELDEN_Creator.mp4",f"✅ <b>{html.escape(plan['title'][:120])}</b>\n📱 {html.escape(platform)} · ⏱ {round(final_duration)}s · 🎞️ {len(scenes)} مشاهد\n{mode_info.label} · 🎙️ {VOICE_TONE_LABELS[voice_tone]} · 📝 كتابة ديناميكية",operation_id)
        timings["total"]=time.perf_counter()-started
        await event("creator","timings",", ".join(f"{k}={v:.1f}s" for k,v in timings.items()),operation_id=operation_id,telegram_id=uid,metadata=timings)
        record_media(uid,"video",idea,"creator");await db.update_creator_job(job_id,"completed");await complete_checkpoint(job_id)
        if delivery.success:
            await safe_delete_message(status)
            try:
                thumb=work/"ELDEN_Thumbnail.jpg";await create_thumbnail(images[0],plan["title"],thumb)
                await deliver_path(message.bot,message.chat.id,"photo",thumb,"ELDEN_Thumbnail.jpg","🖼 غلاف مقترح")
                pack=await publishing_pack(plan["title"],plan["narration"],platform,lang)
                await message.answer(html.escape(pack[:3900]))
            except Exception: log.exception("Creator extras failed")
        else: await safe_edit_text(status,"✅ تم إنشاء الفيديو وحفظه. تعذر تأكيد الإرسال؛ لن تتم مضاعفة الإرسال تلقائياً.")
    except Exception as exc:
        log.exception("Creator workflow failed for %s",uid);await db.update_creator_job(job_id,"failed",str(exc));await db.update_operation(operation_id,status="failed",generation_status="failed",error=str(exc),error_code="creator")
        if not quota_committed and uid not in settings.admin_ids: await db.refund_video_quota(uid)
        await safe_edit_text(status,"❌ تعذر إكمال المحتوى. تم تسجيل المرحلة التي حدث فيها الخلل.")
    finally:
        if creator_folder is not None:_track(delete_creator_folder_later(creator_folder, delay=3600))
        running.discard(uid)


def _track(coro) -> None:
    task = asyncio.create_task(coro); tasks.add(task); task.add_done_callback(tasks.discard)


async def start_creator_request(message: Message, idea: str, lang: str, platform: str = "reel", creator_mode: str = "balanced") -> None:
    _track(run_creator(message, idea, platform, lang, creator_mode))


@router.message(Command("creator"))
@router.message(F.text.in_({"🎬 صانع المحتوى", "🎬 Content Creator", "🎬 Créateur"}))
async def creator_page(message: Message):
    await message.answer("🎬 <b>AI Content Creator</b>\nاختر نوع المحتوى القصير:", reply_markup=platform_keyboard())


@router.callback_query(F.data.startswith("creator:"))
async def choose_creator(callback: CallbackQuery):
    platform = callback.data.split(":", 1)[1]
    if platform == "cancel":
        wizards.pop(callback.from_user.id, None)
        await callback.message.edit_text("تم إلغاء العملية.")
        return await safe_callback_answer(callback)
    if platform not in {"reel", "tiktok", "instagram", "youtube"}:
        return await safe_callback_answer(callback, "اختيار غير صالح", show_alert=True)
    user = await db.get_user(callback.from_user.id) or {}
    wizards[callback.from_user.id] = {"platform": platform, "lang": user.get("language", "dz")}
    await callback.message.edit_text("🎬 اختر مستوى إنتاج الريلز:", reply_markup=creator_mode_keyboard())
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("creator_mode:"))
async def choose_creator_mode(callback: CallbackQuery):
    mode_key = callback.data.split(":", 1)[1]
    if mode_key not in MODES:
        return await safe_callback_answer(callback, "اختيار غير صالح", show_alert=True)
    state = wizards.get(callback.from_user.id)
    if not state:
        return await safe_callback_answer(callback, "انتهت العملية، ابدأ من جديد.", show_alert=True)
    state["creator_mode"] = mode_key
    info = get_mode(mode_key)
    await callback.message.edit_text(f"{info.label}\n{info.description}\n\n💡 أرسل فكرة المحتوى وحدد المدة، مثلاً: مستقبل الذكاء الاصطناعي في 30 ثانية.")
    await safe_callback_answer(callback)


@router.message(InCreatorWizard(), F.text)
async def creator_idea(message: Message):
    state = wizards.get(message.from_user.id)
    if not state:
        return
    if "creator_mode" not in state:
        return await message.answer("اختر وضع الإنتاج أولاً.", reply_markup=creator_mode_keyboard())
    state = wizards.pop(message.from_user.id)
    await start_creator_request(message, message.text.strip(), state["lang"], state["platform"], state["creator_mode"])
