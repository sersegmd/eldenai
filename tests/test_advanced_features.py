from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path

try:
    import aiohttp  # noqa: F401
except ModuleNotFoundError:
    sys.modules["aiohttp"] = types.ModuleType("aiohttp")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("DASHBOARD_PASSWORD", "test-password")

from app import ai_client
from app.context_memory import clear_context, context_summary, record_media, resolve_media_followup
from app.document_context import extract_document_text
from app.captioning import CaptionWord, build_ass


def test_context() -> None:
    uid = 99101
    clear_context(uid)
    record_media(uid, "image", "a silver Lamborghini in a dark studio", "generated")
    result = resolve_media_followup(uid, "اجعلها حمراء")
    assert result and result[0] == "image"
    assert "Lamborghini" in result[1] and "حمراء" in result[1]
    assert "Recent session media context" in context_summary(uid)
    clear_context(uid)


def test_documents() -> None:
    text = extract_document_text("مرحبا من الملف".encode(), "note.txt", "text/plain")
    assert "مرحبا" in text
    assert extract_document_text(b"x", "archive.zip", "application/zip") == ""


def test_dynamic_captions() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "captions.ass"
        build_ass([
            CaptionWord("كتابة", 0.0, 0.7),
            CaptionWord("ديناميكية", 0.7, 1.5),
            CaptionWord("احترافية", 1.5, 2.3),
        ], output)
        content = output.read_text(encoding="utf-8-sig")
        assert "\u202b" in content and "كتابة" in content and "MarginV" in content
        assert "\\kf" in content

        english = Path(folder) / "captions_en.ass"
        build_ass([
            CaptionWord("Dynamic", 0.0, 0.7),
            CaptionWord("captions", 0.7, 1.5),
        ], english)
        assert "\\kf" in english.read_text(encoding="utf-8-sig")


async def test_ai_helpers() -> None:
    captured = []

    async def fake(messages, temperature=0.7):
        captured.append((messages, temperature))
        return "ok"

    original = ai_client._ollama_chat
    ai_client._ollama_chat = fake
    try:
        result = await ai_client.chat([{"role": "user", "content": "hello"}], "friendly", mode="coding", context_note="last image: car")
        assert result == "ok"
        system = captured[-1][0][0]["content"]
        assert "senior software engineer" in system and "last image: car" in system

        async def fake_plan(messages, temperature=0.7):
            return '```json\n{"title":"Demo","narration":"Hello","scenes":[{"visual_prompt":"scene one","seconds":5}]}\n```'

        ai_client._ollama_chat = fake_plan
        plan = await ai_client.generate_creator_plan("idea", 30, "reel", "ar")
        assert plan["title"] == "Demo" and plan["scenes"][0]["visual_prompt"] == "scene one"

        captured.clear()
        ai_client._ollama_chat = fake
        await ai_client.describe_image(b"abc", "describe")
        assert captured[-1][0][-1]["images"] == ["YWJj"]
    finally:
        ai_client._ollama_chat = original


def test_static_integration() -> None:
    root = Path(__file__).resolve().parents[1]
    bot = (root / "app/bot.py").read_text()
    creator = (root / "app/creator.py").read_text()
    captioning = (root / "app/captioning.py").read_text()
    whisper_service = (root / "whisper_service.py").read_text()
    actions = (root / "app/message_actions.py").read_text()
    modes = (root / "app/modes.py").read_text()
    db = (root / "app/db.py").read_text()
    image = (root / "app/image.py").read_text()
    video = (root / "app/video.py").read_text()

    assert bot.index("is_creator_request(message.text)") < bot.index("resolve_command_intent(message.text)")
    assert bot.index("resolve_media_followup(uid, message.text)") < bot.index("resolve_command_intent(message.text)")
    assert "actions_keyboard(token)" in bot
    assert "clear_context(message.from_user.id)" in bot
    assert "tempfile.mkdtemp(prefix=\"elden_creator_\")" in creator
    assert "delete_creator_folder_later(creator_folder, delay=3600)" in creator
    assert "generate_creator_plan" in creator and "synthesize_speech" in creator and "_assemble" in creator
    for tone in ("news", "documentary", "storyteller", "anime_storyteller"):
        assert f'"{tone}"' in creator
    assert "create_dynamic_captions" in creator
    assert "fade=t=in" in creator and "fade=t=out" in creator and "zoompan" in creator
    assert "Premium production quality" in creator and "coherent recurring subjects" in creator
    assert "narration_segment" in creator and "_normalized_scene_durations" in creator
    assert "scene_durations" in creator and "scene_00.mp4" not in creator
    assert "\\kf" in captioning and "word_timestamps" in whisper_service
    for label in ("قراءة بالصوت", "إعادة الصياغة", "ترجمة", "اختصار", "شرح", "إعادة التوليد"):
        assert label in actions
    for key in ("quick", "deep", "research", "creative", "coding", "study", "business", "creator"):
        assert f'"{key}"' in modes
    assert "ai_mode TEXT NOT NULL DEFAULT 'quick'" in db
    assert "client.generate" not in image and "reserve_image_quota" not in image
    assert "محرك API غير مربوط" in image
    assert 'record_media(uid, "video"' in video


if __name__ == "__main__":
    test_context()
    test_documents()
    test_dynamic_captions()
    asyncio.run(test_ai_helpers())
    test_static_integration()
    print("Advanced features/context/modes/actions/creator: PASS")
