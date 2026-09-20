# 📐 خطة تطوير Ayman OS Agent — النسخة المعتمدة

> هذه الوثيقة هي المرجع المتفق عليه للبناء القادم. أي تعديل عليها يُناقش أولاً.

**تاريخ الاعتماد:** 2026-09-20
**الحالة:** معتمدة — في انتظار بدء التنفيذ

---

## 1) القرارات المعتمدة ✅

| القرار | الاختيار |
|--------|----------|
| الكتابة على Google Sheets من التيليجرام | **نعم — الآن** (gspread + Service Account) |
| قناة تقرير الوالد | **تيليجرام فقط** (البريد يبقى اختيارياً وليس شرطاً للتشغيل) |
| مزود الذكاء الاصطناعي | **Bedrock + Gemini معاً** (auto مع fallback) |
| المنطقة الزمنية | **Asia/Riyadh** لكل الجدولة والتقارير |
| أدوات shell/الملفات من تيليجرام | **تُحذف نهائياً** (ثغرة أمنية) |
| قاعدة البيانات | **Google Sheets هو مصدر الحقيقة الوحيد** — لا ملفات JSON على قرص الحاوية |

---

## 2) المعمارية المستهدفة

```
GitHub ──push──▶ CI (pytest + ruff) ──▶ Railway (Dockerfile فقط)
                                            │
                            عملية واحدة: بوت تيليجرام (polling)
                            + APScheduler داخلي (Asia/Riyadh)
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
             طبقة البيانات              الوكيل الذكي            المجدول
             gspread قراءة+كتابة        Function Calling         • تقرير يومي 21:00
             (Service Account)          أدوات JSON Schema        • تنبيه قبل الموعد
                    │                   + أوامر مباشرة           • متابعة السلسلة اليومية
                    ▼                   + ذاكرة جلسة قصيرة
        Google Sheets (خاص، مشترك مع SA فقط)
        │ Config │ Courses │ DailyLog │ Schedule │ Tasks │ Appointments │ Alerts │
                                            │
                              تيليجرام: الطالب + الوالد
```

**مبادئ ثابتة:**
- default-deny: لا أحد يستخدم البوت إلا إذا كان في `TELEGRAM_CHAT_ID`.
- لا أسرار ولا بيانات حقيقية في الريبو إطلاقاً (لا sheet ID، لا chat IDs).
- كل بيانات المستخدم تعيش في الشيت؛ قرص الحاوية للكاش المؤقت فقط.

---

## 3) مراحل التنفيذ (بالترتيب)

### المرحلة 1 — 🚨 الأمان والنظافة (أولاً، دائماً)
- [ ] حذف `run_command` و`read_file` و`write_file` من `OSAgent` ومن أي مسار يصل إليه تيليجرام.
- [ ] `TELEGRAM_CHAT_ID` إلزامي: إن فُضيت القائمة → البوت يرفض الجميع ويحذّر في اللوج.
- [ ] إزالة رابط الشيت الحقيقي من `config.py` وchat IDs الحقيقية من `.env.example`.
- [ ] إضافة `TIMEZONE` (افتراضي `Asia/Riyadh`) وتصحيح كل `datetime.now()` عبر `zoneinfo`.
- [ ] توحيد النشر: حذف `Procfile` والإبقاء على `Dockerfile` + `railway.json`.

### المرحلة 2 — 📊 طبقة البيانات: قراءة وكتابة
- [ ] استبدال تنزيل XLSX بـ **gspread** عبر Service Account (متغير `GOOGLE_SERVICE_ACCOUNT_JSON` — يقبل JSON أو Base64).
- [ ] كاش في الذاكرة (TTL ~60 ثانية) لتقليل استدعاءات API.
- [ ] المواعيد تنتقل إلى تاب **Appointments** في الشيت (تنتهي مشكلة الفقدان مع إعادة النشر).
- [ ] تاب **Tasks** للمهام الدراسية.
- [ ] أوامر الكتابة: `/log <كود> <دقائق>` ← DailyLog، `/done <مهمة>` ← Tasks، `/appt` ← Appointments.
- [ ] عدم توفر Service Account → البوت يعمل بوضع قراءة فقط مع رسالة واضحة (لا انهيار).

### المرحلة 3 — 🤖 عقل الوكيل: Function Calling
- [ ] تعريف الأدوات بصيغة JSON Schema: `log_study`, `mark_done`, `add_appointment`, `get_summary`, `get_risk`, `send_parent_report`, `ask_tutor`.
- [ ] تنفيذ عبر Bedrock Converse API (tool use) + Gemini function calling، بنفس مخطط الأدوات.
- [ ] الإبقاء على الأوامر المباشرة (`/summary`, `/risk`, ...) كمسار سريع واحتياطي عند تعطل الـ AI.
- [ ] تحقق صارم من مخرجات الأداة قبل التنفيذ (whitelist، لا نص حر يمر للنظام).
- [ ] ذاكرة جلسة قصيرة لكل chat (آخر ~10 رسائل، في الذاكرة).

### المرحلة 4 — ⏰ الجدولة والاستباقية
- [ ] APScheduler داخل عملية البوت.
- [ ] تقرير يومي 21:00 توقيت الرياض → تيليجرام للطالب والوالد (البريد اختياري عبر `/sendreport` فقط).
- [ ] تنبيه قبل كل موعد من تاب Appointments بساعة (قابل للضبط).
- [ ] تنبيه ذكي: إذا لم يُسجل الطالب أي جلسة حتى 20:00 → تذكير لطيف.
- [ ] `/status` يعرض آخر تشغيل للمجدول وآخر مزامنة للشيت.

### المرحلة 5 — 🧪 الجودة والنشر
- [ ] اختبارات pytest لطبقة الشيت (بملفات وهمية) والأدوات والتقارير.
- [ ] GitHub Actions: `pytest` + `ruff` على كل push.
- [ ] تحديث README ليطابق النظام الجديد.
- [ ] مراجعة: `boto3` يبقى (قرار Bedrock+Gemini) مع استيراد كسول، وإعادة تسمية `BedrockService` إلى `AIService`.

---

## 4) مهمتك الآن: إنشاء Google Service Account 🔑

> مرة واحدة فقط، ~10 دقائق. النتيجة: ملف JSON لا تشاركه مع أحد، وُيوضع في Railway فقط.

1. ادخل [console.cloud.google.com](https://console.cloud.google.com) وأنشئ مشروعاً جديداً باسم مثل `study-mentor-os`.
2. من القائمة: **APIs & Services → Library** → فعّل **Google Sheets API** و**Google Drive API**.
3. **APIs & Services → Credentials → Create Credentials → Service Account**:
   - الاسم: `ayman-os-agent` ← ثم Create → Done (تخطَّ الخطوتين الاختياريتين).
4. افتح الـ Service Account → تبويب **Keys → Add Key → Create new key → JSON** ← يُنزّل ملف `.json`. **هذا هو مفتاحك السري.**
5. افتح الملف وانسخ بريد الحساب (ينتهي بـ `@....iam.gserviceaccount.com`).
6. في Google Sheets: افتح شيت Study Mentor OS → **مشاركة** → أضف بريد الـ SA بصلاحية **Editor**.
7. 🔒 **خصخصة الشيت:** Share → على رابط "Anyone with the link" → غيّره إلى **Restricted**.
8. في Railway → خدمتك → **Variables** → أضف متغيراً باسم `GOOGLE_SERVICE_ACCOUNT_JSON` والقيمة = **محتوى ملف JSON كاملاً** (انسخه كما هو).

> ⚠️ لا تضع ملف الـ JSON في الريبو أبداً. Railway فقط (أو `.env` محلياً للتجربة).

### متغيرات البيئة الجديدة (سأضيفها لـ `.env.example` عند البناء)
```bash
GOOGLE_SERVICE_ACCOUNT_JSON={...محتوى الملف أو نسخة Base64 منه...}
TIMEZONE=Asia/Riyadh
DAILY_REPORT_TIME=21:00
SHEET_CACHE_TTL_SECONDS=60
```
وتبقى `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`, `AWS_*` كما هي.

---

## 5) ما تم رفضه صراحة ❌ (حتى لا يعود في نقاش لاحق)

| المقترح | سبب الرفض |
|---------|-----------|
| n8n / Make / no-code | منطق AI محدود، ولا كود في Git |
| استبدال الشيت بـ Supabase/SQLite | نخسر رؤية الوالد المباشرة — الشيت هو المنتج |
| إبقاء أدوات shell/ملفات | ثغرة تسريب أسرار من تيليجرام |
| Webhook بدل polling | لاحقاً فقط إن ظهرت حاجة — polling أبسط وأكثر تسامحاً |
| تشغيل نسختين من البوت (محلي + Railway) | تعارض `409 Conflict` في getUpdates — نسخة واحدة فقط |
