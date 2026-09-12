# مواصفات روبوت MatrixRobotQC

## الهوية
- الاسم: MatrixRobotQC
- النوع: QuantConnect / LEAN Python algorithm
- الصنف: `MatrixRobotQC(QCAlgorithm)`
- الملف: `robot/MatrixRobotQC_main.py` (نسخة للاستشارة)

## الكون / البيانات
- قائمة رموز في `MATRIX_SYMBOLS` (فوركس رئيسي + تقاطعات + ذهب/فضة)
- `AddForex(symbol, Resolution.Hour, Market.OANDA)`
- Warmup: `MIN_WARMUP` (~220 ساعة)

## المنطق (ملخص)
- إشارة ensemble مرجّحة
- مرشحات ICT / session / volatility
- مجلس (council) للموافقة/الرفض
- إدارة مخاطرة + قيود prop + قفل طوارئ
- ارتباط بين الرموز
- scalp مبسّط (مشروط)

## خارج النطاق داخل QC
- تنفيذ MT5 الحقيقي
- عقل GPT الحي أثناء الشغل
- ذاكرة VPS / سجلات الدورات الحية

## معايير نجاح أول Backtest (مقترح)
- اكتمل بدون Runtime Error
- عدد صفقات > 0 (وإلا تشخيص الإشارة)
- تقرير يحفظ: Net Profit, Sharpe, Drawdown, Win Rate, Total Orders
- مقارنة فترتين مختلفتين على الأقل قبل أي تفاؤل

## ملاحظات للمراجع
راجع العتبات في أعلى الملف (`SIGNAL_NORM_THRESHOLD`, `MIN_STRENGTH`, `META_SCORE_MIN`, …) — تغيّرت عبر جولات (Round 3: أقل صفقات / جودة أعلى). خطر الـ overfitting موجود؛ اطلب اختبارات ثبات.
