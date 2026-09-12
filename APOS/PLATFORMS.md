# كتالوج منصات المنظومة — من قائمتك الخطية

## أ) منصات فحص واختبار الروبوتات / الاستراتيجيات

| # | المنصة | Plugin ID | الدور |
|---|--------|-----------|--------|
| 1 | QuantConnect | `quantconnect` | Backtest سريع + تقارير (تعديل الكود عبر Cursor) |
| 2 | TrendSpider | `trendspider` | مسح/شارتات واستراتيجيات |
| 3 | TradingView | `tradingview` | أفكار ومؤشرات ومتابعة يومية |
| 4 | Trade Ideas (Holly AI) | `tradeideas` | تقييم تلقائي |
| 5 | MetaTrader 5 Strategy Tester | `metatrader5` | تقييم تلقائي |
| 6 | Build Alpha | `buildalpha` | تقييم/توليد تلقائي |
| 7 | StrategyQuant X | `strategyquant` | تقييم/توليد تلقائي |
| 8 | Composer | `composer` | اختبار سيمفونيات/محافظ |
| 9 | TradeStation (Walk Forward) | `tradestation` | تحسين Walk-Forward |
| 10 | Forex Strategy Builder | `forexsb` | بناء/فحص FX |
| 11 | AlgoTrader | `algotrader` | خوارزميات مؤسسية |
| 12 | NinjaTrader | `ninjatrader` | اختبار استراتيجيات (عقود…) |

**مجموعة التقييم التلقائي (حسب ورقتك):** Trade Ideas · MT5 · Build Alpha · StrategyQuant X

**مجموعة فحص الأفكار/المؤشرات اليومية:** TradingView (+ TradeStation ضمن أدوات المتابعة)

## ب) منصات فحص أنظمة الذكاء الاصطناعي

| # | المنصة | Plugin ID | الدور |
|---|--------|-----------|--------|
| 1 | LangSmith | `langsmith` | تتبع وتقييم LLM |
| 2 | Phoenix (Arize) | `phoenix` | Observability |
| 3 | DeepEval | `deepeval` | اختبارات LLM |
| 4 | SonarQube | `sonarqube` | جودة الكود |
| 5 | Promptfoo | `promptfoo` | تقييم الـ prompts |
| 6 | *(فارغ في الورقة)* | — | أرسل الاسم لاحقاً |

## ج) بنية البيانات (مبنية بالكامل في v0.5)

| مكوّن | التنفيذ |
|--------|---------|
| Memory Agent | `cos/agents/memory_agent.py` |
| Supervisor Agent | `cos/agents/supervisor_agent.py` |
| Data Layer | `cos/data/` (SQL + Redis + Vector + Timeseries) |
| PostgreSQL | عبر `COS_DATABASE_URL` + docker-compose |
| TimescaleDB | صورة timescale في docker-compose + جدول metrics |
| Redis | `COS_REDIS_URL` أو ذاكرة محلية تلقائياً |
| Qdrant | `COS_QDRANT_URL` أو فهرس متجه محلي JSON |

حالياً بدون Docker: SQLite + Redis-memory + Vector محلي — نفس الواجهات البرمجية.


## القاعدة

كل منصة = **هوية دخول + استكشاف + خبرة** — لا برمجة يدوية لكل زر مسبقاً.
