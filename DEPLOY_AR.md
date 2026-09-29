# 🚀 تشغيل البوت دائماً بدون جهازك (Render المجاني)

الهدف: البوت يعمل 24/7 في السحابة، بلا جهازك، وبلا بطاقة بنكية.

## لماذا وقع الاختيار على Render؟

- **مجاني وبدون بطاقة بنكية**، وبإمكان المساعد إنشاء الخدمة وضبطها عبر **API** بالكامل.
- يدعم بناء `Dockerfile` مباشرة من مستودع GitHub عام.
- عيوبه التي عوّضناها تلقائياً:
  1. الخطة المجانية **تُنيم** الخدمة بعد 15 دقيقة بلا زيارات → عوّضناه بمنبّهين.
  2. **لا قرص دائم** → عوّضناه بنسخ احتياطي تلقائي لقاعدة SQLite إلى مستودع خاص.
  3. عنوان الـIP الخارجي **غير ثابت** → لأجل مفتاح Supercell (انظر القسم 5).

## البنية

```
تيليجرام  ⇄  بوت Python (Render مجاني: clash-tactician.onrender.com)
                    │
                    ├── /health            نقطة صحة (تستخدمها المنصات والمنبّهات)
                    ├── قاعدة SQLite       في /data داخل الحاوية (غير دائم)
                    │      └── نسخ احتياطي كل 15 دقيقة → مستودع خاص clash-tactician-data
                    └── تسجيل IP الخارجي كل 6 ساعات في سجلات Render

المنبّهات (لمنع النوم):
  • Cloudflare Worker cron كل 5 دقائق        (الأساسي)
  • GitHub Actions كل 15 دقيقة               (احتياطي)
```

## 1) إنشاء الخدمة (يقوم به المساعد عبر API)

المطلوب منك مرة واحدة فقط: **مفتاح Render API** (Account Settings ← API Keys ← Create API Key).

بعدها يُنشئ المساعد تلقائياً:
- خدمة Web Service من نوع Docker من المستودع `ammar-alfifi/clash-tactician`، فرع `main`.
- الخطة `free` والمنطقة `Frankfurt`، ومسار الفحص `/health`.
- متغيرات البيئة كاملة من ملف `.env` لديك.

## 2) متغيرات البيئة على Render

| المتغير | ملاحظة |
|---|---|
| `TELEGRAM_BOT_TOKEN` | من BotFather |
| `COC_API_TOKEN` | مفتاح Supercell |
| `AI_KEY_ENCRYPTION_KEY` | نفسه الموجود في `.env` وإلا لا تُفك مفاتيح المستخدمين المشفّرة |
| `OPENROUTER_API_KEY` | المفتاح الافتراضي المشترك |
| `OPENROUTER_MODEL` / `OPENROUTER_FALLBACK_MODELS` / `OPENROUTER_BASE_URL` | اختيارية |
| `DEFAULT_LANGUAGE` | `ar` |
| `WAR_REMINDER_INTERVAL_MINUTES` | 60 افتراضياً |
| `BACKUP_GIT_REMOTE` | `git@github.com:ammar-alfifi/clash-tactician-data.git` |
| `BACKUP_SSH_KEY` | مفتاح نشر للكتابة فقط بصيغة base64 (أنشأه المساعد) |
| `BACKUP_INTERVAL_SECONDS` | 900 |

> `PORT` تضبطه Render تلقائياً، والبوت يستمع عليه لخدمة `/health`.

## 3) ما يحدث عند إعادة التشغيل

1. البوت يقرأ نسخة قاعدة البيانات من المستودع الخاص (**استعادة تلقائية**).
2. يبدأ polling + مهمة تذكيرات الحرب.
3. كل 15 دقيقة يرفع نسخة متّسقة (SQLite `VACUUM INTO`) إلى المستودع الخاص.
4. فشل النسخ لا يوقف البوت أبداً؛ يُسجَّل فقط ويُعاد في الدورة التالية.

## 4) التحديثات

- أي `git push` إلى `main` يعيد النشر تلقائياً على Render.
- لمتابعة السجلات: من لوحة Render ← الخدمة ← Logs، أو عبر API.

## 5) مفتاح CoC API وIP المتغيّر (مهم)

Render المجاني يستخدم **نطاقات IP مشتركة**، فقد يتغيّر IP الخدمة عند إعادة النشر أو إعادة التشغيل. لذلك:

1. البوت يسجّل IP الخارجي في السجلات (`Egress IP: ...`) عند الإقلاع وكل 6 ساعات.
2. عند تغيّره: ادخل <https://developer.clashofclans.com> ← **My Account → API Keys** ← حرّر المفتاح ← ضع IP الجديد ← احفظ.
3. اختبر:
   ```bash
   curl -s "https://api.clashofclans.com/v1/locations" \
     -H "Authorization: Bearer <COC_API_TOKEN>" | head -c 200
   ```
   ظهور JSON يعني أن المفتاح يعمل، ورسالة `accessDenied.invalidIp` تعني أن عليك تحديث الـIP.

> إن أردت ثباتاً كاملاً لميزات اللعبة مستقبلاً: خادم صغير مجاني للأبد مثل **Oracle Always Free** (يتطلب بطاقة للتحقق فقط) يعطي IP ثابتاً، والمشروع جاهز للنقل إليه عبر `docker compose up -d --build` (انظر `docker-compose.yml`).

## 6) استكشاف الأخطاء

| العَرَض | الحل |
|---|---|
| البوت لا يرد | تأكد من عدم تشغيل نسخة محلية بنفس التوكن (polling مزدوج يُعطّل الاثنين). |
| تأخّر ~دقيقة في أول رسالة بعد خمول طويل | طبيعي: Render يُنيم الخدمة، والمنبّه يعيدها. حدّث المنبّهات إن تكرر. |
| `accessDenied.invalidIp` | حدّث IP المفتاح في لوحة Supercell (القسم 5). |
| اختفاء بيانات بعد إعادة نشر | تأكد من ضبط `BACKUP_GIT_REMOTE` و`BACKUP_SSH_KEY`، وراجع سجلات «Database backup pushed/restored». |
| تذكيرات الحرب لا تصل | `/subscribe` في المجموعة المرتبطة، ومفتاح CoC يعمل. |
| تعطّل فك تشفير المفاتيح | `AI_KEY_ENCRYPTION_KEY` يجب أن يطابق المفتاح القديم. |
