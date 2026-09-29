# 🚀 تشغيل البوت دائماً بدون جهازك

الهدف: يعمل البوت 24/7 في السحابة دون الحاجة لإبقاء جهازك مفتوحاً.

## لماذا لا يمكن استخدام Cloudflare Workers مثل مشروع MineWarr؟

مشروع MineWarr كان **JavaScript** ويعمل **بلا سيرفر دائم** (webhook)، لذلك ناسبه Cloudflare Workers.
أما هذا البوت فهو **Python (aiogram)** ويحتاج:

- عملية دائمة تعمل بلا توقف (polling) + مهمة خلفية لتذكيرات الحرب.
- قاعدة **SQLite** محلية.
- **عنوان IP ثابت** لأن واجهة Supercell الرسمية ترفض أي IP غير مسجَّل في لوحة المطورين (رسالة `accessDenied.invalidIp`)، وCloudflare Workers يستخدم عناوين متناوبة غير ثابتة.

لذلك الخيارات المناسبة هي حاويات/خوادم صغيرة:

| الخيار | التكلفة | بطاقة بنكية؟ | IP ثابت؟ | ملاحظة |
|---|---|---|---|---|
| **justrunmy.app** | 0$ ضمن الطبقة المجانية (0.15 CPU / 256MB / 0.3GB) | لا | يتغير عند إعادة النشر غالباً | حاوية تعمل دائماً بلا نوم — الأسهل |
| **Oracle Cloud Always Free** | 0$ للأبد | نعم (للتحقق فقط) | ✅ مضمون | الأفضل لعمل ميزات اللعبة بثبات |
| Hugging Face Space | 0$ | لا | لا | ينام بعد 48 ساعة بلا زيارات وبدون IP ثابت |
| VPS/Fly.io مدفوع (~5$/شهر) | 5$ | نعم | ✅ | الأبسط والأرسخ |

---

## القيم المطلوبة (في كل الخيارات)

انسخ القيم من ملف `.env` على جهازك وأضفها كمتغيرات بيئة في المنصة:

| المتغير | إلزامي؟ | ملاحظة |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | من BotFather |
| `COC_API_TOKEN` | ✅ لميزات اللعبة | يحتاج تحديث IP الخادم (القسم 5) |
| `AI_KEY_ENCRYPTION_KEY` | ✅ لخطط الهجوم | نفس المفتاح الحالي وإلا تعطّل فك تشفير المفاتيح المحفوظة |
| `OPENROUTER_API_KEY` | مستحسن | المفتاح الافتراضي المشترك |
| `OPENROUTER_MODEL` / `OPENROUTER_FALLBACK_MODELS` / `OPENROUTER_BASE_URL` | اختياري | لها قيم افتراضية |
| `SUPPORT_CHAT_ID` | اختياري | لاستقبال تذاكر الدعم |
| `WAR_REMINDER_INTERVAL_MINUTES` | اختياري | الافتراضي 60 |
| `DEFAULT_LANGUAGE` | اختياري | الافتراضي `ar` |

> ⚠️ لا تضع القيم في Git أو في رسائل عامة.

---

## الخيار 1: justrunmy.app (مجاني بدون بطاقة — الأسهل)

1. أنشئ حساباً على <https://justrunmy.app> (بريد إلكتروني فقط، بدون بطاقة).
2. من لوحة التحكم: **Create application** ← النشر من **Git** ← اربط GitHub واختر مستودع `ammar-alfifi/clash-tactician` وفرع `main`.
3. نوع النشر: **Dockerfile** (الملف موجود جاهزاً في المشروع).
4. المنفذ: `8080`، ومسار فحص الصحة: `/health`.
5. أضف متغيرات البيئة من الجدول أعلاه.
6. اضغط **Deploy**، ثم راقب السجلات حتى ترى:
   - `Health server listening on port 8080`
   - `Run polling for bot @...`
7. بعد نجاح التشغيل، افتح **Web Shell** من اللوحة ونفّذ:

   ```bash
   curl -s https://api.ipify.org
   ```

   سجّل هذا العنوان في لوحة Supercell (القسم 5).

ملاحظات:
- عند إعادة النشر قد يتغير عنوان IP الخارجي؛ أعد التحقق من `curl -s https://api.ipify.org` وحدّثه في اللوحة عند تغيّره.
- الطبقة المجانية تكفي بوتاً صغيراً؛ لا ترفع فيها الذاكرة عن حدّها المجاني قدر الإمكان.

---

## الخيار 2: Oracle Cloud Always Free (0$ للأبد + IP ثابت)

### 1) إنشاء الحساب والخادم

1. سجّل في <https://www.oracle.com/cloud/free/> (يُطلب بطاقة للتحقق فقط، والطبقة Always Free لا تُحاسَب).
2. أنشئ VM بنظام **Ubuntu 24.04** وشكل مناسب للطبقة المجانية (مثل `VM.Standard.E2.1.Micro`، أو `VM.Standard.A1.Flex` إن توفّر في منطقتك).
3. أضف مفتاح SSH العام من جهازك (`~/.ssh/id_ed25519.pub` أو `id_rsa.pub`).
4. بعد الإنشاء: **Networking → Reserved public IPs** واحجز العنوان واربطه بالخادم حتى **لا يتغير أبداً** عند إعادة التشغيل.

### 2) التثبيت

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker

git clone https://github.com/ammar-alfifi/clash-tactician.git
cd clash-tactician
nano .env        # الصق القيم من الجدول أعلاه

docker compose up -d --build
docker compose logs -f
```

تحقق:

```bash
curl http://127.0.0.1:8080/health     # يجب أن يعيد {"status": "ok"}
curl -s https://api.ipify.org          # عنوان IP الخادم (سجّله في لوحة Supercell)
```

### 3) خدعة عدم اعتبار الخادم خاملاً

Oracle قد تستعيد خوادم Always Free إذا اعتبرتها خاملة. أضف نبضة CPU دورية بسيطة:

```bash
(crontab -l 2>/dev/null; echo "*/15 * * * * timeout 120 nice -n 19 sha256sum /dev/zero >/dev/null 2>&1") | crontab -
```

### 4) التحديث لاحقاً

```bash
cd clash-tactician && git pull && docker compose up -d --build
```

---

## 3) نقل بياناتك الحالية (اختياري)

قاعدة البيانات الحالية صغيرة (حساباتك ولاعبك المرتبط). تنقل على خادم Docker/Compose هكذا:

```bash
# على جهازك: انسخ الملف إلى الخادم
scp data/bot.sqlite3 ubuntu@<عنوان-الخادم>:/home/ubuntu/

# على الخادم داخل مجلد المشروع
docker compose cp /home/ubuntu/bot.sqlite3 clash-tactician:/data/bot.sqlite3
docker compose exec -u 0 clash-tactician chown botuser:botuser /data/bot.sqlite3
docker compose restart clash-tactician
```

على justrunmy.app لا تتوفر مساحة دائمة للأfiles؛ أعد ربط حسابك ولاعبك من داخل تيليجرام بعد النشر.

---

## 5) تحديث مفتاح CoC API (مهم)

1. ادخل إلى <https://developer.clashofclans.com> بحسابك.
2. **My Account → API Keys** ثم **Create New Key** (أو حرّر المفتاح الحالي).
3. في خيار قيود العنوان ضع **Public IP** الخادم (الذي حصلت عليه من `curl -s https://api.ipify.org`).
4. احفظ، وانتظر بضع دقائق حتى ينتشر التغيير.
5. اختبر من الخادم:

   ```bash
   curl -s "https://api.clashofclans.com/v1/locations" \
     -H "Authorization: Bearer <COC_API_TOKEN>" | head -c 200
   ```

   إذا ظهرت بيانات JSON فالمفتاح يعمل. إذا ظهر `accessDenied.invalidIp` فراجع الخطوة 3.

> إذا كنت تستخدم جهازك أيضاً مع البوت، فإن مفتاح Supercell يسمح بعنوان IP واحد لكل مفتاح؛ أنشئ مفتاحاً ثانياً لجهازك إن أردت الاثنين معاً.

---

## 6) استكشاف الأخطاء

| العَرَض | الحل |
|---|---|
| البوت لا يرد إطلاقاً | تأكد من عدم تشغيل نسخة ثانية بنفس التوكن (المحلية أو السحابية)؛ التزامن المزدوج يعطل polling. أوقف المحلية عند تشغيل السحابية. |
| المنصة تقول unhealthy | تأكد أن المنفذ `8080` مضبوط ومسار الفحص `/health`. |
| فقدان البيانات بعد إعادة النشر | استخدم خادماً بقرص دائم (Oracle/Docker Compose)، فطبقة justrunmy المجانية مساحتها صغيرة وغير دائمة. |
| `accessDenied.invalidIp` من واجهة GoC | حدّث IP المفتاح في لوحة Supercell (القسم 5). |
| تعطّل فك تشفير مفاتيح المستخدمين | تأكد أن `AI_KEY_ENCRYPTION_KEY` نفسه الموجود في `.env` المحلي. |
| تذكيرات الحرب لا تصل | تأكد من `/subscribe` في المجموعة المرتبطة وأن `COC_API_TOKEN` يعمل. |