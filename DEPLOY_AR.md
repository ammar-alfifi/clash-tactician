# 🚀 تشغيل البوت دائماً بدون جهازك (Render المجاني — تم النشر ✅)

البوت يعمل الآن 24/7 في السحابة بدون جهازك وبدون بطاقة بنكية.

## الحالة الحالية

| البند | القيمة |
|---|---|
| رابط الخدمة | <https://clash-tactician.onrender.com> |
| فحص الصحة | <https://clash-tactician.onrender.com/health> |
| معرّف الخدمة | `srv-dau16g893c1s73cbddl0` (خطة `free` — منطقة فرانكفورت) |
| IP الخروج | `74.220.51.162` (ثابت أثناء التشغيل — انظر القسم 5) |
| منع النوم | Cloudflare Worker `clash-tactician-keepalive` كل 5 دقائق + GitHub Actions كل 15 دقيقة |
| النشر التلقائي | `.github/workflows/deploy.yml` عند كل `push` إلى `main` |
| النسخ الاحتياطي | كل 15 دقيقة إلى مستودع خاص `clash-tactician-data` (تم التحقق فعلياً) |
| ملف الإعدادات المحلي | `~/.config/coc-bot/cloud.json` + مفتاح Render في `~/.config/coc-bot/render_api_key` |

### فحص سريع للحالة الكاملة

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/.config/coc-bot/cloud.json'))['diag_token'])")
curl -s "https://clash-tactician.onrender.com/diag?token=$TOKEN&current=1&coc=1" | python3 -m json.tool
```

يعرض: IP الخروج الحالي، عدد المستخدمين/اللاعبين المرتبطين، ونتيجة اختبار مفتاح Supercell.

## لماذا Render؟

- **مجاني وبدون بطاقة بنكية**، ويمكن إدارة الخدمة بالكامل عبر API.
- يبني `Dockerfile` مباشرة من مستودع GitHub.
- عيوبه التي عوّضناها:
  1. تُنيم الخدمة بعد 15 دقيقة بلا زيارات → منبّهان (Cloudflare كل 5 دقائق + Actions كل 15 دقيقة).
  2. لا قرص دائم → نسخ احتياطي تلقائي لقاعدة SQLite إلى مستودع خاص + استعادة عند الإقلاع.
  3. IP غير مضمون الثبات → القسم 5.

## البنية

```
تيليجرام  ⇄  بوت Python (Render: clash-tactician.onrender.com)
                    │
                    ├── /health   نقطة صحة للمنصة والمنبّهات
                    ├── /diag     تشخيص محمي برمز (IP + عدّادات + اختبار CoC + `&clans=` لجلب بيانات قبائل عامة)
                    ├── قاعدة SQLite في /data  → نسخ احتياطي كل 15 دقيقة → مستودع خاص
                    └── مهمة تذكيرات الحرب + تسجيل IP الخروج

المنبّهات: Cloudflare Worker cron (كل 5 دقائق) + GitHub Actions (كل 15 دقيقة)
```

## 1) إعادة إنشاء الخدمة (لو احتجت لاحقاً)

المفتاح محفوظ محلياً في `~/.config/coc-bot/render_api_key`. الإنشاء عبر API:

```bash
curl -X POST https://api.render.com/v1/services \
  -H "Authorization: Bearer $(cat ~/.config/coc-bot/render_api_key)" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "web_service", "name": "clash-tactician",
    "ownerId": "tea-dau15ju0tbcc73fj7jug",
    "repo": "https://github.com/ammar-alfifi/clash-tactician",
    "branch": "main", "autoDeploy": "no",
    "serviceDetails": {
      "env": "docker", "region": "frankfurt", "plan": "free",
      "healthCheckPath": "/health",
      "envSpecificDetails": {"dockerfilePath": "./Dockerfile"}
    }
  }'
```

ثم أضف متغيرات البيئة (القسم 2)، وأطلق النشر:

```bash
curl -X POST https://api.render.com/v1/services/srv-dau16g893c1s73cbddl0/deploys \
  -H "Authorization: Bearer $(cat ~/.config/coc-bot/render_api_key)" \
  -H "Content-Type: application/json" -d '{"clearCache":"do_not_clear"}'
```

> ملاحظة: Render لا يستطيع النشر التلقائي من رابط مستودع عام دون ربط تطبيق GitHub، لذلك يتولى `deploy.yml` إطلاق النشر عبر API عند كل push.

## 2) متغيرات البيئة على Render

| المتغير | ملاحظة |
|---|---|
| `TELEGRAM_BOT_TOKEN` | من BotFather |
| `COC_API_TOKEN` | مفتاح Supercell |
| `AI_KEY_ENCRYPTION_KEY` | نفسه الموجود في `.env` وإلا لا تُفك مفاتيح المستخدمين المشفّرة |
| `OPENROUTER_API_KEY` | المفتاح الافتراضي المشترك |
| `DEFAULT_LANGUAGE` / `WAR_REMINDER_INTERVAL_MINUTES` | اختيارية |
| `DATABASE_PATH` | `/data/bot.sqlite3` |
| `BACKUP_GIT_REMOTE` | `git@github.com:ammar-alfifi/clash-tactician-data.git` |
| `BACKUP_SSH_KEY` | مفتاح نشر كتابة-فقط بصيغة base64 |
| `BACKUP_INTERVAL_SECONDS` | 900 |
| `DIAG_TOKEN` | رمز حماية نقطة التشخيص |

> `PORT` تضبطه Render تلقائياً والبوت يستمع عليه.

## 3) النسخ الاحتياطي والاستعادة

1. عند الإقلاع: يقرأ البوت نسخة قاعدة البيانات من المستودع الخاص إن لم توجد محلياً.
2. كل 15 دقيقة: يأخذ لقطة متّسقة (`VACUUM INTO`) ويرفعها إلى المستودع الخاص.
3. فشل النسخ لا يوقف البوت، ويُعاد في الدورة التالية.

## 4) التحديثات

- أي `git push` إلى `main` → GitHub Actions يطلق نشراً جديداً تلقائياً.
- السجلات من لوحة Render ← الخدمة ← Logs، أو من DashBoard.
- لا تشغّل نسخة محلية بنفس التوكن في نفس الوقت (polling مزدوج يعطّل النسختين).

## 5) مفتاح CoC API وIP الخروج (مهم)

1. IP الخروج الحالي: **`74.220.51.162`** (اختبرناه 5 مرات متتالية وكان ثابتاً).
2. حدّثه في <https://developer.clashofclans.com> ← **My Account → API Keys** ← حرّر المفتاح ← ضع الـIP ← احفظ (قد يحتاج دقائق لينتشر).
3. تحقّق مباشرة من داخل السحابة:

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/.config/coc-bot/cloud.json'))['diag_token'])")
curl -s "https://clash-tactician.onrender.com/diag?token=$TOKEN&coc=1" | python3 -m json.tool
```

- `"ok": true` → ميزات اللعبة تعمل.
- `accessDenied.invalidIp` → أعد تحديث الـIP في اللوحة.

> ملاحظة: قد يتغيّر IP الخروج بعد إعادة نشر أو إعادة تشغيل للخدمة؛ لا حاجة لأي مراقبة — نفّذ أمر الفحص أعلاه وراجع `current_egress_ip` وحدّث اللوحة عند الحاجة.

## 6) استكشاف الأخطاء

| العَرَض | الحل |
|---|---|
| البوت لا يرد | تأكد من عدم تشغيل نسخة محلية بنفس التوكن. |
| تأخر أول رسالة بعد خمول طويل | طبيعي بعد نومة نادرة؛ المنبّه يعيده خلال دقائق. |
| `accessDenied.invalidIp` | حدّث IP المفتاح (القسم 5). |
| اختفاء بيانات بعد إعادة نشر | راجع سجلات «Restored database backup» و«Database backup pushed». |
| تذكيرات الحرب لا تصل | `/subscribe` في المجموعة المرتبطة + مفتاح CoC يعمل. |
| تعطّل فك تشفير المفاتيح | `AI_KEY_ENCRYPTION_KEY` يجب أن يطابق المفتاح القديم. |
