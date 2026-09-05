from __future__ import annotations
from dataclasses import dataclass
from math import ceil

@dataclass(frozen=True)
class CreatorMode:
    key: str
    label: str
    description: str
    animate_fraction: float

MODES = {
    "fast": CreatorMode("fast", "⚡ سريع", "صور سينمائية بحركة مونتاج سريعة", 0.0),
    "balanced": CreatorMode("balanced", "🎯 متوازن", "تحريك أهم المشاهد مع بديل تلقائي", 0.5),
    "cinematic": CreatorMode("cinematic", "🎬 سينمائي", "تحريك جميع المشاهد ومونتاج كامل", 1.0),
}

def get_mode(key: str) -> CreatorMode:
    return MODES.get(key, MODES["balanced"])

def animated_scene_indices(mode_key: str, scenes: list[dict]) -> list[int]:
    mode = get_mode(mode_key)
    if not scenes or mode.animate_fraction <= 0:
        return []
    if mode.animate_fraction >= 1:
        return list(range(len(scenes)))
    target = max(1, ceil(len(scenes) * mode.animate_fraction))
    scored = []
    for index, scene in enumerate(scenes):
        try:
            importance = float(scene.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5
        if index == 0:
            importance += 0.35
        if index == len(scenes) - 1:
            importance += 0.15
        motion = str(scene.get("motion_prompt") or "").lower()
        if any(word in motion for word in ("run", "fly", "move", "orbit", "tracking", "drone", "ركض", "يطير")):
            importance += 0.2
        scored.append((importance, index))
    return sorted(index for _, index in sorted(scored, reverse=True)[:target])
