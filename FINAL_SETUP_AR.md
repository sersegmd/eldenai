# ELDEN AI — التثبيت النهائي

## المتطلبات
- Windows 10/11
- Python 3.13 للبوت وPython 3.11 لـ OpenAI Whisper (يمكن تثبيتهما معاً)
- Node.js 18+ مع npx
- مفاتيح Telegram وOllama وPollinations

## التشغيل
1. فك الضغط في مجلد جديد.
2. شغّل `setup_windows.bat` وأنشئ `.env`، أو انسخ `.env` القديم ثم أضف `POLLINATIONS_API_KEY`.
3. شغّل `start_windows.bat` فقط.
4. الملف يشغّل Agnes وWhisper ولوحة الإدارة والبوت.

## أهم إعدادات .env
```env
POLLINATIONS_API_KEY=sk_your_key
WHISPER_MODEL=small
AGNES_AUTO_START=true
AGNES_START_COMMAND=npx free-short-video --no-open
FREE_IMAGE_DAILY_LIMIT=20
PRO_IMAGE_DAILY_LIMIT=250
VIP_IMAGE_DAILY_LIMIT=1000
```

## الميزات
- محادثة Ollama متعددة اللغات وسياق مؤقت.
- رسائل صوتية: OpenAI Whisper ثم إجابة كتابية.
- صور Pollinations بنموذج مختار تلقائياً، ستايل ومقاس وحصص.
- فيديو Agnes مع اختيار المدة والتنزيل الموثوق.
- Telegram Stars وخطط Free/Pro/VIP.
- إحالات بمكافآت صور وكوبونات.
- SQLite دائم ولوحة إدارة.

## الأوامر
`/start` `/image` `/video` `/new` `/personality` `/plans` `/referral` `/redeem CODE` `/admin`

إنشاء كوبون للأدمن:
`/coupon CODE pro 30 100 25`
