# COS Personal — v0.5 Full Stack

لا يوجد تأجيل للمعمارية الأساسية: وكلاء + بيانات + أمان + لوحة + Plugins.

## التشغيل

```text
open_system.bat       → الواجهة الموحّدة (صوت + شات)
open_dashboard.bat    → لوحة المراقبة
open_remote.bat       → خادم الهاتف وحده (اختياري)
```

## الصوت (مثل ChatGPT Voice)

زر **🎧 محادثة**: اضغط مرة واحدة فقط.

- يستمع إليك تلقائياً حتى تتوقف عن الكلام ثم يرد فوراً
- STT: `faster-whisper` محلي (تشغيل `setup_whisper.bat`) مع احتياطي Google
- لإنهاء الجلسة كلها: الزر الأحمر **إيقاف الجلسة** (ليس لكل جملة)

زر **🔊 نطق** يتحكم بنطق ردود الشات النصي أيضاً.

## الهاتف (مراقبة + أوامر)

1. شغّل `open_system.bat` ثم اضغط زر **هاتف**
2. من هاتفك على **نفس الواي فاي** افتح: `http://IP-اللابتوب:8787`
3. راقب الشات، أرسل أوامر، أو اضغط إيقاف

خارج البيت: استخدم [Tailscale](https://tailscale.com) (أسهل) أو نفقاً مثل ngrok إلى المنفذ `8787`.

خدمات اختيارية كاملة:

```powershell
cd APOS
docker compose up -d
copy .env.example .env
```

بدون Docker يعمل تلقائياً على: **SQLite + Redis-memory + Vector محلي**.

## الطبقات المبنية

| طبقة | التنفيذ |
|------|---------|
| Data | SQL (SQLite/Postgres) · Redis · Qdrant/Vector · Timeseries/metrics |
| Memory | قصيرة · طويلة · متجهة · Experience JSON |
| Agents | Coding · Quant · Trading · Research · Business · Marketing · Memory · Supervisor |
| Safety | Blocklist · Permissions · Activity log · Kill switch · Confirm |
| UI | Chat موحّد + Dashboard |
| Plugins | 19 منصة (روبوتات + LLM eval) |

## العقل (v0.8) — llama.cpp أولاً

الترتيب الافتراضي (`COS_BRAIN_PROVIDER=auto` أو `llamacpp`):

1. **llama.cpp** على `http://127.0.0.1:8080` (أسرع محلياً)
2. **Ollama** إن لم يعمل llama.cpp
3. **OpenRouter** إن وُجد مفتاح
4. **Anthropic نصي** إن وُجد مفتاح

إعداد سريع:

```text
setup_llamacpp.bat     → تنزيل الخادم + نموذج Qwen2.5-3B
start_llamacpp.bat     → تشغيل الخادم (اترك النافذة مفتوحة)
setup_whisper.bat      → تعرّف كلام محلي أدق (مرة واحدة)
check_brain.bat        → اختبار الاتصال
open_system.bat        → واجهة COS
```

طلب فحص روبوت: «اطلب ملف الروبوت وافحصه في كوانت كونكت» → دورة `matrix_cycle` v6 (ليس Trade Ideas).

في الشات: `حالة العقل`

تصعيد Claude Computer Use للرؤية: `COS_AUTO_CLAUDE_ESCALATE=1` + مفتاح Anthropic.

## تغطية المخطط (v0.6)

تقدير محدّث بعد رفع الطبقات الناقصة:

| الطبقة | قبل | الآن |
|--------|-----|------|
| Orchestrator / Goals / Priority / Scheduler | ~40% | **~75%** |
| Execution Browser/Terminal/Files | ~35% | **~70%** |
| World Model + Processes | ~15% | **~55%** |
| Plugins (فتح كتالوج) | ~35% | **~55%** |
| Dashboard | ~40% | **~60%** |

**إجمالي تقديري للمخططات: ~65%–70%** (كان ~50%).
المتبقية الأكبر: أتمتة عميقة داخل كل منصة، Vision/OCR أقوى، استقلال 24/7 أنضج.


الحلقة الافتراضية:

`فشل محلي → بحث إنترنت + ذاكرة + AI نصي → إجراءات بديلة → إعادة محاولة → تصعيد Claude رؤية إن لزم → حفظ الدرس`

الإعدادات في `.env`:

```
COS_AUTO_RESEARCH=1
COS_AUTO_RESEARCH_RETRIES=2
COS_AUTO_CLAUDE_ESCALATE=1
```

المنظومة **محلية أولاً**، ثم **تنفتح على الإنترنت تلقائياً** عند العجز — دون انتظار أمر «ابحث».
