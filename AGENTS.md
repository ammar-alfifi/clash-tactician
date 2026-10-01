# AGENTS.md — دليل الوكلاء لمشروع Clash Tactician

هذا الملف يُقرأ تلقائياً في كل محادثة جديدة داخل هذا المستودع. اقرأه كاملاً قبل أي عمل.
**تواصل المالك بالعربية** — اجعل ردودك ودلائل المستخدم بالعربية، بينما يبقى الكود والتعليقات البرمجية بالإنجليزية.

## 1) نظرة عامة على المشروع

- بوت تيليجرام عربي للاعبي Clash of Clans: بيانات اللاعب/القبيلة/الحرب، تخطيط هجوم بالذكاء الاصطناعي، مفاتيح AI مشفّرة، تذكيرات حرب تلقائية.
- التقنيات: Python 3.11+ (الفينف المحلي 3.14)، aiogram 3، aiohttp، aiosqlite، cryptography، Pillow.
- البنية: `app/` مقسّمة إلى طبقات — `core/` (أخطاء، تنسيق، وقت، سجلات)، `storage/` (SQLite ومستودعات)، `coc/` (عميل API، نماذج، كتالوج، خدمة)، `ai/` (مزودون، خزنة مفاتيح، اختيار إعدادات)، `planner/` (مخطط، برومبت، رسم، خدمة)، `bot/` (حالات، أزرار، بطاقات، وسائط، معالجات)، `services/` (لقطات، تذكيرات، مراقب)، `ops/` (صحة، تشخيص، IP الخروج، نسخ احتياطي).
- الاختبارات: `tests/` (65 اختباراً). الأوامر:

  ```bash
  .venv/bin/python -m pytest -q
  .venv/bin/python -m ruff check .
  ```

- الملفات: `README.md` و`DEPLOY_AR.md` و`PLAN_AR.md` بالعربية. `Dockerfile` + `docker-compose.yml` جاهزان.
- الأسرار في `.env` (مُستثنى من Git). لا تضع أي سرّ في المستودع (عام).

## 2) حالة النشر الحالية (تم 2026-09-29)

| البند | القيمة |
|---|---|
| المنصة | Render — خطة `free` (بدون بطاقة بنكية) |
| الخدمة | `clash-tactician` — المعرّف `srv-dau16g893c1s73cbddl0` |
| الرابط | https://clash-tactician.onrender.com |
| المنطقة | `frankfurt` — المالك `tea-dau15ju0tbcc73fj7jug` |
| النشر | Docker من مستودع GitHub العام `ammar-alfifi/clash-tactician` فرع `main` |
| النشر التلقائي | `.github/workflows/deploy.yml` يستدعي Render API عند كل push (Render لا يدعم auto-deploy لرابط مستودع عام) |
| منع النوم | Cloudflare Worker `clash-tactician-keepalive` (cron كل 5 دقائق) + `.github/workflows/keep-alive.yml` (كل 15 دقيقة) |
| النسخ الاحتياطي | كل 15 دقيقة إلى مستودع خاص `ammar-alfifi/clash-tactician-data` (مفتاح نشر كتابة-فقط) |
| IP الخروج | `74.220.51.162` — مسجَّل في لوحة Supercell ويعمل (`coc.ok = true`) |
| الصحة | `/health` |
| التشخيص | `/diag?token=<DIAG_TOKEN>` — يدعم `&current=1` (IP لحظي) و`&coc=1` (فحص مفتاح Supercell) و`&ai=1` (فحص مفتاح AI) و`&plan=1` (فحص شامل للمخطط: صورة→JSON→تحقق) و`&clans=#TAG,#TAG` (جلب بيانات قبائل عامة + حروبها عبر IP السحابي، لأن المفتاح مقيد بعنوان IP واحد) |

### الأسرار والإعدادات على جهاز المالك (خارج المستودع)

- `~/.config/coc-bot/render_api_key` — مفتاح Render API (600). نفسه موجود كسرّ GitHub باسم `RENDER_API_KEY`.
- `~/.config/coc-bot/cloud.json` — معرّف الخدمة، `DIAG_TOKEN`، الرابط، IP، مستودع النسخ الاحتياطي.
- `~/.ssh/coc_bot_backup` — مفتاح النشر للكتابة في مستودع النسخ الاحتياطي (العام منه مُسجَّل كـ deploy key).
- `~/.ssh/coc_bot` / `coc_bot.pub` — مفتاح SSH مُعدّ مسبقاً للانتقال المحتمل إلى خادم/VPS.
- Cloudflare: الحساب مسجَّل عبر wrangler في `~/.config/.wrangler`. ثنائي wrangler موجود في `telegram-miniapp/node_modules/.bin/wrangler` (لا يوجد تثبيت عام).

### قواعد حرجة للوكلاء

1. **لا تشغّل البوت محلياً** (`python -m app`) بينما نسخة السحابة حيّة — Telegram يسمح بعملية polling واحدة؛ التشغيل المزدوج يُعطّل الاثنتين (تعارض 409). أوقف خدمة Render أولاً (`POST /services/<id>/suspend`) ثم أعدها (`/resume`).
2. لا تطبع قيم الأسرار ولا تُدرجها في أي ملف داخل المستودع.
3. أي تعديل كود: شغّل `ruff` و`pytest` ثم `git push` (GitHub Actions ينشر تلقائياً).
4. تغيير متغيرات Render لا يعيد النشر وحده: بعد `PUT /services/<id>/env-vars` أطلق `POST /services/<id>/deploys`.
5. مفتاح CoC مرتبط بعنوان IP واحد: عند إعادة تشغيل الخدمة قد يتغير IP الخروج (`/diag?...&current=1`)، وعندها يحدّث المالك الـIP في <https://developer.clashofclans.com> ← My Account → API Keys ← تحرير المفتاح ← IP جديد.
6. حدّث `DEPLOY_AR.md` عند أي تغيير في البنية.

## 3) أداة إدارة Render (جاهزة في المستودع)

```bash
python3 deploy/render_api.py GET /services
python3 deploy/render_api.py PUT /services/srv-dau16g893c1s73cbddl0/env-vars /path/to/env_array.json
python3 deploy/render_api.py POST /services/srv-dau16g893c1s73cbddl0/deploys /path/to/body.json
```

المفتاح يُقرأ من `RENDER_API_KEY` أو `~/.config/coc-bot/render_api_key`.

### فحص سريع للحالة

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/.config/coc-bot/cloud.json'))['diag_token'])")
curl -s "https://clash-tactician.onrender.com/diag?token=$TOKEN&current=1&coc=1" | python3 -m json.tool
```

## 4) البنية السحابية (كيف تعمل)

- **بلا قرص دائم** في Render المجاني: `app/persistence.py` يستعيد `bot.sqlite3` من مستودع النسخ الاحتياطي عند الإقلاع، ويرفع لقطة متّسقة (`VACUUM INTO`) كل 15 دقيقة. الفشل لا يوقف البوت.
- **بلا نوم**: منبّهان مستقلان يستدعيان `/health` بانتظام.
- **`app/egress.py`** يتتبع IP الخروج (كل 5 دقائق) ويكشفه عبر `/diag`.
- النسخ الاحتياطي/الاستعادة مُختبران فعلياً (اختبار `tests/test_persistence.py` + تحقق إنتاجي).

## 5) قرارات وقيود تاريخية (لماذا هذه المنصة)

- **Cloudflare Workers مستبعد**: البوت Python يحتاج عملية دائمة + قاعدة SQLite + **IP ثابت** (Supercell يرفض IP غير مسجَّل)، وWorkers يستخدم IPs متناوبة فلا يصلح.
- **justrunmy.app مستبعد**: يلغي الطبقة المجانية في 2026-10-19.
- **Hugging Face Docker Spaces مستبعد**: يتطلب خطة PRO مدفوعة في 2026.
- **Northflank مستبعد**: يطلب بطاقة بنكية إلزامياً للجميع.
- **Render مختار**: مجاني، بلا بطاقة، قابل للأتمتة بالكامل عبر API. عيوبه معوَّضة بالمنبّهات + النسخ الاحتياطي + مراقبة IP.
- **مسار الترقية لاحقاً**: أي VPS (مثل Oracle Always Free إن توفرت بطاقة) يعطي IP ثابتاً دائماً — المشروع جاهز: `git clone && docker compose up -d --build` مع نقل `data/bot.sqlite3` أو الاعتماد على نسخة النسخ الاحتياطي.

## 6) حالة موثّقة

- 65 اختباراً ناجحاً + ruff نظيف.
- أُعيد بناء البوت بالكامل (الإصدار 2.0) بهندسة طبقات أنظف؛ الكود القديم محفوظ في الفرع
  `legacy-v1`. قاعدة البيانات v1 تُرحَّل تلقائياً إلى مخطط `ct_*` عند الإقلاع (بلا فقد بيانات).
- نُقلت قاعدة بيانات المالك إلى السحابة: 4 مستخدمين، لاعب مرتبط واحد؛ النسخ الاحتياطي التلقائي تحقق منه (commit باسم `backup ... UTC`).
- فحص مفتاح Supercell من السحابة: `ok: true` (HTTP 200).
