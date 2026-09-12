# حزمة استشارة المشروع — CONSULTATION PACK

**الغرض:** إرسال هذا المجلد (أو الـ ZIP) إلى ChatGPT / Claude / خبراء QuantConnect / منصات فحص الروبوتات للحصول على رأي مستقل.

**لا يحتوي على مفاتيح API.** المفاتيح تبقى في `APOS/.env` المحلي فقط.

---

## ابدأ من هنا

| ملف | لمن؟ |
|-----|------|
| `00_PROMPT_FOR_CHATGPT.md` | انسخه كاملاً كأول رسالة لأي ذكاء اصطناعي |
| `01_PROJECT_BRIEF_AR.md` | ملخص عربي كامل للوضع |
| `02_PROJECT_BRIEF_EN.md` | English brief for QC / quant platforms |
| `03_QUESTIONS_TO_ASK.md` | أسئلة محددة تريد إجابات عليها |
| `04_ARCHITECTURE_NOW.md` | المعمارية الحالية وما نوصي به |
| `05_ROBOT_SPEC.md` | مواصفات روبوت Matrix على QuantConnect |
| `robot/MatrixRobotQC_main.py` | نسخة من كود الروبوت للفحص |
| `code/qc_executor.py` | منفّذ الـ API المباشر (بلا ماوس) |

---

## مسارات أصلية على الجهاز

```
Windows automation (COS/APOS):
  C:\Users\AkarTech\Downloads\WindowsComputerUse\

Robot (preferred):
  C:\Users\AkarTech\Downloads\MatrixRobot_Handoff_Clean-3\MatrixRobot\artifacts\python-agents\quantconnect\MatrixRobotQC\main.py

Launch QC API backtest (after credentials):
  Desktop\RUN_QC_BACKTEST.bat
```

---

## الحالة بصراحة (جملة واحدة)

حاولنا بناء وكيل Windows عام (صوت + ماوس + متصفح) فدخلنا دائرة ضعيفة؛ القرار الحالي: منفّذون متخصصون — أولهم ربط مباشر بـ QuantConnect API لتشغيل Backtest وإرجاع أرقام.
