# Study Mentor OS — Ayman 📚🤖

وكيل مرشد دراسي ذكي: **بوت تيليجرام** للطالب والوالد، يستخدم **Google Sheets كقاعدة بيانات** (قراءة + كتابة)،
بذكاء اصطناعي عبر **AWS Bedrock + Gemini** (Function Calling)، وتقارير وتذكيرات تلقائية بتوقيت **Asia/Riyadh**.

## المعمارية

```
GitHub ──CI (pytest + ruff)──▶ Railway (Dockerfile)
                                  │
                  بوت تيليجرام (polling) + APScheduler داخلي
                  │                        │
          أدوات آمنة whitelisted       تقرير يومي 21:00
          (Function Calling)           تذكير قبل المواعيد
                  │                    نudge مسائي 20:00
                  ▼
      Google Sheets  ← قراءة + كتابة (gspread + Service Account)
      │ Config │ Courses │ DailyLog │ SessionLog │ Schedule │ Tasks │ Appointments │ Alerts │
                  │
      تيليجرام: الطالب + الوالد (تقرير بريدي اختياري)
```

**مبادئ أمنية:** لا تنفيذ shell، لا قراءة/كتابة ملفات، لا أسرار في الريبو،
default-deny للتيليجرام (من ليس في `TELEGRAM_CHAT_ID` يُرفض).

## النشر على Railway

1. ارفع الريبو إلى GitHub واتصله بـ Railway (يستخدم `Dockerfile` تلقائياً).
2. أضف متغيرات البيئة (انظر `.env.example`):

| المتغير | مطلوب | الوصف |
|---------|-------|-------|
| `TELEGRAM_BOT_TOKEN` | ✅ | توكن البوت من BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | IDs مسموحة مفصولة بفواصل — **فارغة = رفض الجميع** |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ✅ للكتابة | محتوى ملف Service Account JSON (أو Base64) |
| `GOOGLE_SHEET_ID` | ✅ للكتابة | معرف الشيت من رابطه |
| `TIMEZONE` | — | افتراضي `Asia/Riyadh` |
| `DAILY_REPORT_TIME` | — | افتراضي `21:00` |
| `EVENING_NUDGE_TIME` | — | افتراضي `20:00` |
| `REMINDER_MINUTES_BEFORE` | — | افتراضي `60` |
| `TELEGRAM_STUDENT_CHAT_ID` | — | نudge المساء للطالب فقط بدلاً من الجميع |
| `AI_BACKEND` | — | `auto` (افتراضي) / `gemini` / `bedrock` |
| `GEMINI_API_KEY` أو `AWS_*` | ✅ للذكاء | مفتاح Gemini أو مفاتيح Bedrock |
| `PARENT_EMAIL` + `SMTP_*` | — | تقرير بريدي اختياري |

3. انشر — لا حاجة لأي إعداد آخر. فحص الصحة يخدم تلقائياً على `$PORT`.

## إعداد Google Sheets (مرة واحدة)

1. أنشئ **Service Account** في Google Cloud وفعّل Sheets + Drive API
   (الخطوات التفصيلية في `docs/UPGRADE_PLAN.md` القسم 4).
2. شارك الشيت مع بريد الـ SA بصلاحية **Editor**، **ثم اجعل الشيت Restricted**.
3. ضع محتوى مفتاح JSON في `GOOGLE_SERVICE_ACCOUNT_JSON` ومعرف الشيت في `GOOGLE_SHEET_ID`.

التابات المتوقعة: `Config`, `Courses`, `DailyLog`, `Schedule`, `Alerts` (موجودة لديك)،
ويُنشئ الوكيل تلقائياً: `Tasks`, `Appointments`, `SessionLog` عند أول استخدام.

بدون Service Account يعمل البوت بوضع **قراءة فقط** (عبر `AYMAN_STUDY_SHEET_URL` أو `AYMAN_STUDY_SHEET` محلياً).

## أوامر تيليجرام

| الأمر | الوظيفة |
|-------|---------|
| `/summary` | ملخص اليوم (دقائق المسجلة، آخر سجل، توصية) |
| `/risk` | المادة الأعلى مخاطرة وترتيب المواد |
| `/log CS120 45 [ملاحظة]` | تسجيل جلسة مذاكرة في الشيت |
| `/tasks` و `/done واجب` | عرض المهام المفتوحة / إنجاز مهمة |
| `/appt` و `/appt عنوان \| 2026-09-25 \| 18:00` | المواعيد: عرض / إضافة |
| `/report` و `/sendreport` | معاينة تقرير الوالد / إرساله الآن |
| `/ai سؤالك` | سؤال المرشد الذكي |
| `/status` | حالة النظام والمجدول وآخر مزامنة |

**والرسائل الحرة:** اكتب بشكل طبيعي («ذاكرت ساعة ونص على CS120»، «أضف موعد مراجعة بكرة 6») —
الوكيل يفهم ويستخدم الأدوات آلياً (log_study, add_appointment, …) ثم يؤكد لك.

## التشغيل المحلي

```bash
pip install -r requirements.txt
cp .env.example .env   # ثم املأ القيم

python -m ayman_os_agent.agent --status
python -m ayman_os_agent.agent --summary
python -m ayman_os_agent.agent "وش أخطر مادة؟"
python -m ayman_os_agent.telegram_bot     # البوت
python send_daily_report.py               # التقرير الآن
```

> ⚠️ لا تشغّل نسخة محلية والنسخة على Railway في نفس الوقت — يحدث تعارض
> `409 Conflict` في تلقي التحديثات. نسخة واحدة فقط.

## التطوير

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest
```

CI (GitHub Actions) يشغّل `ruff` + `pytest` على كل push.

## هيكل الكود

```
ayman_os_agent/
├── agent.py          # OSAgent: الأدوات الآمنة + حلقة Function Calling + التوجيه السريع
├── ai_service.py     # Bedrock Converse + Gemini function calling (مخطط أدوات موحد)
├── sheet_store.py    # طبقة Google Sheets: قراءة/كتابة + كاش TTL + Service Account
├── study_sheet.py    # سجلات الشيت الدراسي (+ احتياطي XLSX للقراءة فقط)
├── scheduler.py      # المواعيد (تاب Appointments + ترحيل من JSON القديم)
├── tasks.py          # المهام (تاب Tasks)
├── reporting.py      # تقرير الوالد اليومي
├── notifications.py  # تيليجرام + بريد اختياري
├── telegram_bot.py   # الواجهة: أوامر + رسائل حرة + APScheduler + default-deny
├── timeutils.py      # كل منطق الوقت بتوقيت Asia/Riyadh
└── config.py         # الإعدادات (بلا أسرار أو روابط حقيقية)
```
