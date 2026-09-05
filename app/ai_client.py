import base64
import json
import re

import aiohttp
from .config import settings
from .puter_client import puter_chat

BASE_SYSTEM = """You are ELDEN AI, the intelligence inside a multilingual Telegram bot. Respond in the user's language or in a language explicitly requested. You know the bot can: chat and reason with Ollama; write, translate, summarize and help with code; prepare professional image prompts through an image interface whose generation backend may be disabled; create AI videos with Agnes (Simple, Creative, Manuscript, Anchor and Poetry, multiple aspect ratios and durations); understand voice notes with local Whisper; reply with natural speech using Fish Audio when voice mode is enabled or requested; manage temporary chat sessions and user personalities; show Free/Pro/VIP quotas and Telegram Stars subscriptions; handle referrals and coupons; and provide video progress/cancellation. When a user asks to create an image/video or use another bot feature, never say the bot cannot do it; the Telegram command router performs the real action. Never falsely claim an action completed before the router confirms it. In conversational replies, never claim that an image or video is being created, queued, processed, or will be sent later; only the real media workflow may report that status. Never reveal, mention, list or hint at provider names, model names, API names, internal tools, endpoints, infrastructure or implementation details to users; describe every capability only as an ELDEN AI feature. If the user requests an audio reply, answer the requested subject directly. Never mention that voice was requested and never announce conversion, recording, synthesis, delivery, or response format. Be accurate, useful and concise unless detail is requested. Use clean Telegram-friendly formatting. Protect private data and refuse harmful requests while offering safe alternatives."""


async def _openrouter_chat(messages: list[dict], temperature: float = 0.7):
    from .openrouter_client import complete
    return await complete(messages, temperature)


async def _routed_chat(messages: list[dict], temperature: float = 0.7, prefer_advanced: bool = False):
    return await _openrouter_chat(messages, temperature)


async def chat(messages: list[dict], personality: str = "", mode: str = "quick", context_note: str = "", voice_mode: bool = False) -> str:
    mode_rules = {
        "quick": "Give a fast, direct and concise answer.",
        "deep": "Analyze deeply, verify assumptions, compare alternatives and provide a thorough answer.",
        "research": "Use supplied research evidence, separate fact from uncertainty and cite supplied source URLs.",
        "creative": "Prioritize originality, vivid ideas and polished creative output.",
        "coding": "Act as a senior software engineer: diagnose precisely, write robust code and include verification steps.",
        "study": "Teach step by step with clear examples and a concise recap.",
        "business": "Focus on customers, revenue, cost, risk, execution and measurable next steps.",
        "creator": "Optimize for strong hooks, retention, storytelling, calls to action and social media formats.",
    }
    system = BASE_SYSTEM + f"\nActive response mode: {mode_rules.get(mode, mode_rules['quick'])}"
    if personality:
        system += f"\nUser-selected personality: {personality[:1200]}"
    if context_note:
        system += f"\nUse this temporary session context when relevant:\n{context_note[:6000]}"
    if voice_mode:
        system += "\nVoice mode is active: answer professionally and directly in 2-4 short natural sentences, usually under 700 characters. Put the conclusion first, avoid markdown, lists, repetition, introductions and unnecessary detail."
    return await _routed_chat([{'role': 'system', 'content': system}, *messages], temperature=0.7, prefer_advanced=mode in {'deep','research','creative','coding','creator'})


async def classify_media_request(text: str) -> str:
    """Second-stage classifier: direct creation requests must never fall into chat."""
    system = """Classify this Telegram message. Return exactly one lowercase word: video, image, or chat.
video means the user directly asks to generate a new video now.
image means the user directly asks to generate a new image/photo now.
chat means explanations, questions, code, prompt-writing only, or anything else.
Understand Algerian Darija, Arabic, French and English. A polite request is still video/image. Never explain."""
    result = await _openrouter_chat([
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': text[:4000]},
    ], temperature=0.0)
    clean = result.strip().lower().replace('`', '')
    if clean.startswith('video'):
        return 'video'
    if clean.startswith('image'):
        return 'image'
    return 'chat'


async def generate_creator_plan(idea: str, duration: int, platform: str, language: str) -> dict:
    max_scenes = max(2, min(settings.creator_max_scenes, max(2, duration // 2)))
    system = f"""Create a complete short-form content plan for {platform}, exactly about {duration} seconds.
Return valid JSON only with keys: title, narration, voice_tone, visual_style, character_bible, scenes.
voice_tone must be exactly one of: news, documentary, storyteller, anime_storyteller.
Choose the number of scenes naturally from the script's meaning and visual changes. Do not use a fixed interval. Use between 2 and {max_scenes} scenes.
Each scene object must contain narration_segment, visual_prompt, motion_prompt, transition_style, importance and seconds.
motion_prompt describes natural subject and camera movement while preserving identity and anatomy.
transition_style must be one of: independent, continuous, match_cut, keyframes. importance is a number from 0 to 1.
The narration_segment must quote or precisely identify the part of the narration shown by that scene.
The seconds values must reflect the importance and spoken length of each narration segment, and their total must equal {duration} seconds.
The narration must fit the duration, start with a strong hook, remain in the user's language ({language}), and end with a concise call to action.
Infer the requested content type from the user's words. News bulletins use news; documentaries use documentary; stories use storyteller; anime stories use anime_storyteller.
visual_style must define one coherent premium art direction shared by every scene, including recurring subject consistency, palette, lighting and camera language.
Every visual_prompt must be professional and production-ready: exact subject/action, environment, shot size, camera angle, lens, lighting, composition, depth, texture and mood.
All scenes must be visually coherent, cinematic, vertical 9:16, sharp, richly detailed, and contain no captions, logos, watermarks or accidental text."""
    raw = await _routed_chat([{'role': 'system', 'content': system}, {'role': 'user', 'content': idea[:5000]}], temperature=0.55, prefer_advanced=True)
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise RuntimeError("Creator plan was not valid JSON")
    data = json.loads(match.group(0))
    scenes = data.get("scenes") if isinstance(data.get("scenes"), list) else []
    if not scenes:
        raise RuntimeError("Creator plan has no scenes")
    tone = str(data.get("voice_tone") or "documentary").strip().lower()
    if tone not in {"news", "documentary", "storyteller", "anime_storyteller"}:
        tone = "documentary"
    return {
        "title": str(data.get("title") or "ELDEN Creator"),
        "narration": str(data.get("narration") or ""),
        "voice_tone": tone,
        "visual_style": str(data.get("visual_style") or "Premium cinematic visual storytelling with coherent lighting, color and recurring subjects"),
        "character_bible": str(data.get("character_bible") or "Keep recurring characters, clothing, faces, objects, palette and environments visually consistent"),
        "scenes": scenes[:max_scenes],
    }


async def extract_music_query(text: str) -> str:
    system = "Extract only the concise artist and song search query from this request. Return query text only; no quotes, markdown, or explanation."
    result = await _openrouter_chat([{'role': 'system', 'content': system}, {'role': 'user', 'content': text[:1000]}], temperature=0.0)
    return result.replace('`', '').strip()[:200]


async def describe_image(image_bytes: bytes, instruction: str = "") -> str:
    message = {
        'role': 'user',
        'content': instruction or 'Describe this image precisely for future editing context. Mention subjects, colors, composition, lighting and visible text.',
        'images': [base64.b64encode(image_bytes).decode('ascii')],
    }
    return await _openrouter_chat([{'role': 'system', 'content': 'Return a concise factual visual description only.'}, message], temperature=0.2)


async def enhance_video_prompt(text: str, mode: str, width: int, height: int, language: str) -> str:
    aspect = "9:16 vertical" if height > width else "16:9 horizontal" if width > height else "1:1 square"
    if mode in {'manuscript', 'poetry'}:
        goal = (
            "Create a concise but rich cinematic VISUAL STYLE DIRECTION for the supplied source text. "
            "Do not rewrite, translate, summarize, or quote the source. Describe art direction, lighting, camera language, "
            "color palette, continuity, realism, motion quality, composition and negative constraints."
        )
    elif mode == 'anchor':
        goal = (
            "Rewrite the presenter description as a precise digital-anchor appearance prompt. Include age-neutral appearance, "
            "wardrobe, studio, lighting, framing, eye contact, natural gestures and visual consistency. Do not modify speech content."
        )
    else:
        goal = (
            "Rewrite the idea into one production-ready AI video prompt. Preserve the user's intent while adding subject, action, "
            "environment, shot type, camera movement, lighting, color, atmosphere, timing, continuity, realistic motion and quality constraints."
        )
    speech_markers = (
        "كلام", "يتكلم", "تتكلم", "يهدر", "تهدر", "يقول", "تقول", "حوار",
        "صوت", "تعليق صوتي", "ينطق", "تنطق", "بالدارجة", "بالعربية", "عربي",
    )
    has_arabic = any("\u0600" <= char <= "\u06ff" for char in text)
    preserve_arabic_speech = language in {"dz", "ar"} and has_arabic and any(
        marker in text.lower() for marker in speech_markers
    )
    if preserve_arabic_speech:
        output_rule = (
            "Return ONLY the final prompt in the same Arabic or Algerian Darija used by the user. "
            "Never translate the request, dialogue, narration, quoted speech, or voice-over into English. "
            "Preserve every spoken sentence verbatim and clearly label it as Arabic/Darija speech."
        )
    else:
        output_rule = "Return ONLY the final prompt in English."
    system = f"""You are the ELDEN AI video prompt director. {goal}
Target format: {aspect} ({width}x{height}). User language code: {language}.
{output_rule} Do not add a title, markdown, explanations, quotation wrappers or safety commentary.
Avoid copyrighted character names unless the user supplied them. Do not invent text overlays, logos or watermarks.
Keep the final output under 1400 characters."""
    result = await _openrouter_chat([
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': text[:12000]},
    ], temperature=0.55)
    return result[:1600].strip()


async def enhance_image_prompt(text: str, style: str, size: str, language: str) -> str:
    system = f"""You are ELDEN AI's image art director. Rewrite the request as one production-ready image-generation prompt in English.
Preserve intent. Add subject, composition, camera/lens when useful, lighting, colors, materials, atmosphere and quality constraints.
Selected style: {style}. Target size: {size}. User language: {language}.
For logos/posters preserve exact requested wording and place it in quotation marks. Do not add explanations or markdown.
Return only the final prompt, maximum 1400 characters."""
    result = await _openrouter_chat([
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': text[:8000]},
    ], temperature=0.5)
    return result[:1600].strip()


async def health() -> bool:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.get(f"{settings.ollama_base_url}/api/tags") as response:
                return response.status < 400
    except Exception:
        return False


async def generate_publish_pack(title: str, narration: str, platform: str, language: str) -> str:
    system = f"""Create a publication pack for {platform} in language {language}. Return clean plain text with: TITLE, CAPTION, 8 relevant HASHTAGS, FIRST COMMENT, and a concise CTA. Be specific, professional, truthful, and avoid invented facts or provider names."""
    return await _routed_chat([{'role':'system','content':system},{'role':'user','content':f"Title: {title}\nScript: {narration[:7000]}"}],temperature=0.45,prefer_advanced=True)
