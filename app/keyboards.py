from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from .config import settings

MENU_LABELS = {
    'dz': ['💬 محادثة AI', '🎬 إنشاء فيديو', '🖼 إنشاء صورة', '⭐ الباقات', '🎭 الشخصية', '🌍 اللغة', '🎙️ التواصل الصوتي', 'ℹ️ المساعدة', '🎬 صانع المحتوى', '🧠 أوضاع الذكاء', '🎞 تحريك صورة', '📰 مقال إلى ريلز'],
    'ar': ['💬 محادثة AI', '🎬 إنشاء فيديو', '🖼 إنشاء صورة', '⭐ الباقات', '🎭 الشخصية', '🌍 اللغة', '🎙️ التواصل الصوتي', 'ℹ️ المساعدة', '🎬 صانع المحتوى', '🧠 أوضاع الذكاء', '🎞 تحريك صورة', '📰 مقال إلى ريلز'],
    'fr': ['💬 Chat IA', '🎬 Créer une vidéo', '🖼 Créer une image', '⭐ Offres', '🎭 Personnalité', '🌍 Langue', '🎙️ Mode vocal', 'ℹ️ Aide', '🎬 Créateur', '🧠 Modes IA', '🎞 Animer une image', '📰 Article en Reel'],
    'en': ['💬 AI Chat', '🎬 Create video', '🖼 Create image', '⭐ Plans', '🎭 Personality', '🌍 Language', '🎙️ Voice mode', 'ℹ️ Help', '🎬 Content Creator', '🧠 AI Modes', '🎞 Animate image', '📰 Article to Reel'],
}


def main_menu(lang: str = 'dz') -> ReplyKeyboardMarkup:
    labels = MENU_LABELS.get(lang, MENU_LABELS['dz'])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])],
            [KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
            [KeyboardButton(text=labels[4]), KeyboardButton(text=labels[5])],
            [KeyboardButton(text=labels[6]), KeyboardButton(text=labels[7])],
            [KeyboardButton(text=labels[8]), KeyboardButton(text=labels[9])],
            [KeyboardButton(text=labels[10]), KeyboardButton(text=labels[11])],
        ],
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=True,
        input_field_placeholder='اكتب رسالتك إلى ELDEN AI…',
    )


def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='🇩🇿 الدارجة', callback_data='lang:dz'), InlineKeyboardButton(text='العربية', callback_data='lang:ar')], [
        InlineKeyboardButton(text='Français', callback_data='lang:fr'), InlineKeyboardButton(text='English', callback_data='lang:en')]])


def plans_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Pro · {settings.pro_price_stars} ⭐", callback_data='buy:pro')],
        [InlineKeyboardButton(text=f"VIP · {settings.vip_price_stars} ⭐", callback_data='buy:vip')],
    ])
