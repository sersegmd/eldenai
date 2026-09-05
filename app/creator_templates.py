from __future__ import annotations

TEMPLATES = {
    "news": {"label":"📰 خبر","hook":"Open with the single most consequential fact in a precise urgent sentence.","motion":"stable newsroom framing, controlled push-in, factual visual evidence"},
    "documentary": {"label":"🎥 وثائقي","hook":"Open with a surprising documented contrast or unanswered question that creates immediate curiosity.","motion":"slow cinematic dolly, aerial reveals, atmospheric parallax"},
    "story": {"label":"📖 قصة","hook":"Open inside the decisive moment, then create an information gap the viewer must stay to resolve.","motion":"expressive tracking, motivated close-ups, natural environmental movement"},
    "anime": {"label":"🎌 أنمي","hook":"Open with a visually striking conflict and one unresolved dramatic promise.","motion":"dynamic anime camera, controlled impact motion, consistent character identity"},
    "product": {"label":"🛍 منتج","hook":"Open with the customer's painful problem, then reveal the product benefit in one concrete promise.","motion":"premium product orbit, macro detail, clean controlled highlights"},
    "education": {"label":"📚 تعليمي","hook":"Open with a common mistake and promise a useful correction the viewer can apply immediately.","motion":"clear demonstrations, purposeful reframing, visual hierarchy"},
    "business": {"label":"💼 أعمال","hook":"Open with a measurable opportunity, cost, or risk relevant to the target customer.","motion":"confident camera movement, premium office visuals, data-inspired composition"},
}

def choose_template(text: str) -> tuple[str,dict]:
    value=text.lower()
    rules=[("anime",("انمي","أنمي","anime")),("news",("خبر","اخبار","أخبار","news")),("product",("منتج","اعلان","إعلان","product")),("education",("تعليم","اشرح","درس","learn")),("business",("اعمال","أعمال","شركة","business")),("story",("قصة","حكاية","story")),("documentary",("وثائقي","documentary"))]
    for key,words in rules:
        if any(word in value for word in words): return key,TEMPLATES[key]
    return "documentary",TEMPLATES["documentary"]

def enrich_idea(text: str) -> tuple[str,str]:
    key,template=choose_template(text)
    instruction=(f"CONTENT TEMPLATE: {key}. PROFESSIONAL HOOK RULE: {template['hook']} "
                 "The hook must be truthful, specific, concise, non-clickbait, and create immediate retention without greetings. "
                 f"MOTION LANGUAGE: {template['motion']}. USER IDEA: {text}")
    return key,instruction
