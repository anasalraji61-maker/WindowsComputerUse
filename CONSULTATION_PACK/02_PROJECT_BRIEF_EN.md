# Project Brief (English) — for QuantConnect / quant reviewers

## Goal
Get a **measurable cloud backtest** of `MatrixRobotQC` on QuantConnect, then decide next iteration. Stop relying on Windows mouse/browser automation as the primary executor.

## Robot under test
- Single-file LEAN/QC algorithm: `robot/MatrixRobotQC_main.py` (copy)
- Class: `MatrixRobotQC(QCAlgorithm)`
- Universe: major FX + XAUUSD/XAGUSD via `AddForex(..., Market.OANDA)`, hourly
- Dates: configured near 2023→2024 in code constants `QC_START` / `QC_END`
- Stack inside one file: ensemble signal, ICT filters, MTF/session/vol, council, risk, prop constraints, emergency lock, correlation, simplified scalp
- Explicitly **out of scope for QC**: live MT5 bridge, online GPT brain, VPS memory logs

## Automation wrapper (COS/APOS)
Windows agent that can chat/voice and previously tried to operate QuantConnect UI with mouse paste/click. That path is unreliable.

## Preferred executor (already coded)
`code/qc_executor.py` → QuantConnect REST API v2:
authenticate → upsert project/files → compile → backtest → write markdown stats report.

Requires:
- `QC_USER_ID`
- `QC_API_TOKEN`
from https://www.quantconnect.com/settings/ (Security)

## What we need from you
1. Review algorithm risks for QC (data, brokerage model, warmup, lookahead, overfitting).
2. Recommended backtest protocol (in-sample / out-of-sample / walk-forward lite).
3. Whether Lean CLI cloud is better than raw REST for this workflow.
4. Alternative validation platforms if QC is not enough.
5. A 7–14 day execution plan with success metrics (not UI demos).

## Non-goals for v1
- Fully autonomous Windows computer-use agent
- Live trading automation
- Bypassing user login/2FA responsibilities
