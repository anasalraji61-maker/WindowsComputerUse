# المعمارية الحالية والتوصية

## ما كان مبنياً (مسار ضعيف)

```
User (voice/text)
   → COS UI
   → Intent / Clarify / LLM
   → Planner → workflow (matrix_cycle)
   → Mouse + Browser QuantConnect UI
   → Handoff markdown (غالباً بلا أرقام موثوقة)
```

## ما نوصي به الآن (مسار قوي)

```
User command: "افحص الروبوت"
   → Router (اختيار منفّذ فقط)
   → QC Executor (API)
        locate main.py
        → upload project
        → compile
        → backtest
        → stats report
   → Reply with numbers + report path
```

منفّذون لاحقون محتملون (كل واحد مهمة واحدة):
- `qc_executor` — فحص سحابي
- `report_publisher` — تلخيص للمستخدم/ChatGPT
- `mt5_bridge` — لاحقاً وفقط بعد نجاح الفحص
- `voice_io` — إدخال/إخراج فقط، بلا قرار تنفيذ

## قاعدة ذهبية
العقل السحابي **يفهم ويختار المسار**.  
المنفّذ **لا يتفلسف** — ينفّذ عقداً ثابتاً ويرجع نجاح/فشل + أرقام.
