# وكيل ويندوز — Computer Use حقيقي (ماوس + لوحة مفاتيح أمام عينيك)

هذا **ليس** Docker. يتحكم بسطح مكتب Windows مباشرة عبر PyAutoGUI.

## أمان مهم
- ألغِ أي مفتاح API ظهر سابقاً في محادثة/صورة، واستخدم مفتاحاً جديداً فقط في ملف `.env`
- لا تضع المفتاح في الشات
- للإيقاف الطارئ: حرّك الماوس بسرعة إلى **الزاوية اليسرى العليا**
- لا تشغّله على حسابات بنكية أو كلمات سر إلا وأنت تراقب

## التثبيت (مرة واحدة)

افتح PowerShell:

```powershell
cd C:\Users\SK.6.4\Downloads\WindowsComputerUse
pip install -r requirements.txt
pip install pyperclip
copy .env.example .env
notepad .env
```

ضع في `.env` مفتاحك الجديد:

```
ANTHROPIC_API_KEY=sk-ant-...مفتاحك_الجديد...
ANTHROPIC_MODEL=claude-sonnet-4-5
MAX_STEPS=40
```

## التشغيل

```powershell
cd C:\Users\SK.6.4\Downloads\WindowsComputerUse
python agent.py "افتح Chrome وافتح موقع quantconnect.com"
```

أو بدون مهمة ليطلب منك كتابتها:

```powershell
python agent.py
```

## أمثلة مهام مفيدة لمشروعك

```powershell
python agent.py "في متصفح QuantConnect المفتوح، اذهب لتبويب Logs وابحث عن MATRIX ثم انسخ أول سطر تقرير"
```

```powershell
python agent.py "افتح Notepad واكتب Hello من الوكيل"
```

## إن ظهر خطأ API عن نوع الأداة
جرّب في `.env`:
```
ANTHROPIC_MODEL=claude-haiku-4-5
```
أو أخبرني بنص الخطأ لأعدّل نوع `computer_...` و beta header.

## ملاحظة عن الرصيد
كل خطوة = لقطة شاشة + استدعاء API. راقب رصيدك في console.anthropic.com.
