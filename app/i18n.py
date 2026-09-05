HELP_AR = """ℹ️ <b>دليل ELDEN AI الكامل</b>

<b>البدء والقائمة</b>
/start — تشغيل البوت وفتح الواجهة
/menu — إظهار أزرار القائمة عند الحاجة
/help — عرض هذا الدليل
/cancel — إلغاء المعالج أو الطلب الحالي

<b>المحادثة والصوت</b>
أرسل أي نص للمحادثة مباشرة.
/voice — تفعيل أو إيقاف الرد الصوتي واختيار صوت ذكر أو أنثى
/voicelang auto — اختيار لغة الصوت تلقائياً
/voicelang ar أو fr أو en — تثبيت لغة الصوت
أرسل Voice Note: يحولها البوت إلى نص، يفهمها ثم يرد حسب وضع الصوت.
/new — جلسة جديدة ومسح السياق المؤقت
/personality — تحديد أسلوب وشخصية المساعد
/modes — اختيار وضع سريع، عميق، برمجة، بحث أو صناعة محتوى

<b>الفيديو والمحتوى</b>
/video — اختر النوع، المقاس، والمدة من 5 إلى 20 ثانية ثم أرسل الفكرة
/creator — صناعة Reel/Short كامل؛ يحتاج محرك صور مربوطاً
/animate — أرسل صورة مع وصف الحركة لتحويلها إلى فيديو
/article — أرسل رابطاً أو PDF/DOCX/TXT لتحويل محتواه إلى Reel

<b>الصور</b>
/image — فتح واجهة الصور واختيار الستايل وتحضير البرومبت. التوليد متوقف حتى يتم ربط API مناسب، ولا تُستهلك حصة.

<b>الحساب</b>
/plans — عرض Free/Pro/VIP والاشتراك عبر Telegram Stars
/referral — رابط الدعوة والمكافآت
/redeem CODE — استعمال كوبون
/language — تغيير لغة الواجهة
/privacy — سياسة الخصوصية
/terms — شروط الاستخدام
/paysupport — مساعدة الدفع

<b>أمثلة</b>
«اشرحلي التسويق الرقمي باختصار»
«دير فيديو 20 ثانية عن السياحة في الجزائر»
«حوّل هذا المقال إلى ريلز» ثم أرسل الرابط أو الملف.

<b>الإدارة فقط</b>\n/admin — الإحصائيات ولوحة التحكم\n/coupon CODE plan days max_uses [image_bonus] — إنشاء كوبون"""

HELP_EN = """ℹ️ <b>ELDEN AI complete guide</b>
/start start the bot · /menu show the temporary menu · /help this guide · /cancel cancel the current wizard
/voice enable/disable voice replies and choose male or female · /voicelang auto|ar|fr|en set speech language
Send text or a voice note to chat. /new clears temporary context · /personality customizes the assistant · /modes selects an AI mode.
/video choose type, aspect ratio and 5–20 second duration, then send the idea.
/creator creates a complete Short when an image backend is configured.
/animate sends a photo to image-to-video · /article converts a URL/PDF/DOCX/TXT into a Reel.
/image opens the image UI and prepares a prompt; generation is paused until an API is configured, with no quota consumed.
/plans subscriptions · /referral rewards · /redeem CODE coupon · /language interface language · /privacy privacy · /terms terms · /paysupport payment help.
Admin commands are restricted to administrators."""

HELP_FR = """ℹ️ <b>Guide complet ELDEN AI</b>
/start démarrer · /menu afficher le menu temporaire · /help aide · /cancel annuler l’assistant actif
/voice activer/désactiver les réponses vocales et choisir voix masculine ou féminine · /voicelang auto|ar|fr|en choisir la langue vocale
Envoyez un texte ou un vocal. /new efface le contexte temporaire · /personality personnalise l’assistant · /modes choisit le mode IA.
/video: choisissez type, format et durée de 5 à 20 secondes, puis envoyez l’idée.
/creator crée un Short complet quand un moteur d’images est configuré.
/animate anime une photo · /article transforme URL/PDF/DOCX/TXT en Reel.
/image ouvre l’interface et prépare le prompt; la génération reste suspendue jusqu’à la configuration d’une API, sans quota consommé.
/plans offres · /referral parrainage · /redeem CODE coupon · /language langue · /privacy confidentialité · /terms conditions · /paysupport paiement.
Les commandes administrateur sont réservées aux administrateurs."""

TEXTS = {
    'dz': {
        'welcome': "⚔️ مرحبا بيك في <b>ELDEN AI</b> — ذكاء اصطناعي سريع، خاص ومخصص على ذوقك.",
        'choose_lang': "🌍 اختار اللغة:", 'lang_ok': "✅ تبدلت اللغة بنجاح.",
        'not_verified': "لازم تكمل التحقق أولاً. ابعث /start.", 'blocked': "⛔ حسابك موقوف. تواصل مع الإدارة.",
        'limit': "وصلت للحد اليومي ({limit}). تقدر ترقي الباقة من /plans.",
        'plans': "⭐ <b>الباقات</b>\n\nFree — {free} رسالة + {free_video} فيديو/اليوم\nPro — {pro_limit} رسالة + {pro_video} فيديو/اليوم — {pro_price} ⭐ / {days} يوم\nVIP — {vip_limit} رسالة + {vip_video} فيديو/اليوم — {vip_price} ⭐ / {days} يوم",
        'new': "🧹 بدينا جلسة جديدة ومسحت سياق الجلسة السابقة من الذاكرة.",
        'personality_ask': "🎭 ابعث وصف الشخصية لي تحبها، مثال: «خبير تقني يشرح بالدارجة وباختصار». اكتب /cancel للإلغاء.",
        'personality_ok': "✅ حفظت الشخصية.", 'help': HELP_AR,
        'privacy': "🔐 لا نطلب رقم الهاتف ولا نخزن محتوى محادثاتك. السياق مؤقت؛ نخزن فقط Telegram ID والباقة والاستهلاك.",
        'thinking': "⏳ نفكر…", 'ai_error': "تعذر إكمال الطلب حالياً. حاول مجدداً بعد قليل.",
        'paid': "🎉 تم تفعيل باقة {plan} حتى {date}.", 'cancelled': "تم الإلغاء."
    },
    'ar': {}, 'fr': {}, 'en': {}
}
TEXTS['ar'] = {**TEXTS['dz'], 'welcome': "⚔️ أهلاً بك في <b>ELDEN AI</b> — ذكاء اصطناعي سريع وخاص.", 'help': HELP_AR, 'thinking': "⏳ أفكر…"}
TEXTS['fr'] = {**TEXTS['dz'], 'welcome': "⚔️ Bienvenue sur <b>ELDEN AI</b>.", 'choose_lang': "🌍 Choisissez la langue :", 'lang_ok': "✅ Langue modifiée.", 'not_verified': "Utilisez /start d’abord.", 'blocked': "⛔ Compte suspendu.", 'limit': "Limite quotidienne atteinte ({limit}).", 'new': "🧹 Nouvelle session; ancien contexte effacé.", 'personality_ask': "🎭 Décrivez la personnalité souhaitée. /cancel pour annuler.", 'personality_ok': "✅ Personnalité enregistrée.", 'help': HELP_FR, 'privacy': "🔐 Les conversations restent temporaires; seuls le compte, l’offre et l’utilisation persistent.", 'thinking': "⏳ Réflexion…", 'ai_error': "Impossible de terminer la demande.", 'paid': "🎉 Offre {plan} active jusqu’au {date}.", 'cancelled': "Annulé."}
TEXTS['en'] = {**TEXTS['dz'], 'welcome': "⚔️ Welcome to <b>ELDEN AI</b>.", 'choose_lang': "🌍 Choose a language:", 'lang_ok': "✅ Language updated.", 'not_verified': "Use /start first.", 'blocked': "⛔ Account suspended.", 'limit': "Daily limit reached ({limit}).", 'new': "🧹 New session; previous context cleared.", 'personality_ask': "🎭 Describe your preferred assistant personality. /cancel to stop.", 'personality_ok': "✅ Personality saved.", 'help': HELP_EN, 'privacy': "🔐 Conversations are temporary; only account, plan and usage persist.", 'thinking': "⏳ Thinking…", 'ai_error': "Could not complete the request.", 'paid': "🎉 {plan} active until {date}.", 'cancelled': "Cancelled."}


def t(lang: str, key: str, **kwargs) -> str:
    return TEXTS.get(lang, TEXTS['dz']).get(key, TEXTS['dz'].get(key, key)).format(**kwargs)
