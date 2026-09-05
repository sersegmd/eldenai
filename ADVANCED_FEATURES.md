# ELDEN AI 5.4 — Advanced Features

This release extends the existing bot without replacing its current chat, image, video, voice, payment, quota, referral, coupon, dashboard, or launcher systems.

## New commands

- `/creator` — complete short-form content workflow for Reel, TikTok, Instagram Reel, and YouTube Short.
- `/modes` — Quick, Deep Think, Research, Creative, Coding, Study, Business, and Creator modes.
- `/music` — music search and authorized MP3 preparation.

## Automatic context

Conversation history remains temporary. The bot now also keeps temporary session context for generated images, generated videos, user images, user videos, and supported documents. `/new` clears all temporary conversation and media context.

Supported document context: PDF, DOCX, TXT, Markdown, CSV, JSON, XML, HTML, Python, JavaScript, TypeScript, and CSS. Files are processed temporarily and are not stored by the context feature.

## Content Creator

The creator workflow builds a script, narration, visual scenes, vertical video, a generated ambient music bed, and a final MP4. It uses isolated temporary folders so simultaneous users do not share files. Creator duration is limited by `CREATOR_MAX_DURATION`.

### Automatic narration tone

Creator mode now selects exactly one of four narration tones from the requested content type: News, Documentary, Storyteller, or Anime Storyteller. Explicit words in the request take priority, while ambiguous requests use the content analysis result. The four tones reuse the configured calm-sports, deep, popular, and youth voice references respectively, with tone-specific pacing.

### Dynamic captions and scene motion

Narration is aligned to word timestamps and rendered as highlighted dynamic captions in the social-video safe area. If word alignment is temporarily unavailable, a duration-based fallback keeps captions synchronized. Creator scenes use a shared visual style, stricter professional image prompts, gentle camera motion, color finishing, and reliable cinematic fade transitions before the final audio mix.

### Script-driven scenes

Scene count is no longer calculated from a fixed number of seconds. The content plan chooses natural scene boundaries from the narration, assigns a spoken segment and relative duration to each scene, and generates one context-matched image for each scene. All images must finish first; only then does one visual-render command build the complete scene sequence. Scene durations are normalized to the real narration duration, and temporary creator files are retained for one hour before retry-safe cleanup on Windows.

## Music Finder

Search results show title, artist/channel, duration, a source button, and a selection button. Download and conversion are shown only after the user confirms they have the right to download and use the selected content. Temporary files are deleted automatically.

## Required setup

Run `start_windows.bat`. It installs the updated Python requirements automatically. FFmpeg must be available in PATH for Creator and Music conversion. Existing `.env` and `elden_ai.db` can be reused; the database migration adds the new mode field automatically.
