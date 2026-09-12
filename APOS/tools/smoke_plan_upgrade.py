# -*- coding: utf-8 -*-
from cos.brain.intent import parse_intent, looks_gibberish
from cos.core.router import decide_route, Route, BrainRouter
from cos.core.workflow_engine import load_workflow, HANDLERS

assert looks_gibberish("'+C,$1,H:09'&.C:B%35I3-H")
assert parse_intent("افحص الروبوت في كوانت كونكت", use_llm=False).kind == "qc_matrix"
assert decide_route("اطلب ملف الروبوت").route == Route.COS
assert decide_route("افتح trade ideas").route == Route.TRADING

r = BrainRouter()
r.set_force(Route.QUANT)
d = decide_route("افحص الروبوت", r.force)
assert d.route == Route.COS, d
print("SMOKE_INTENT_OK")

wf = load_workflow("matrix_cycle")
assert "ask_cursor_robot" in HANDLERS
assert "qc_paste_backtest" in HANDLERS
assert "detect_qc_login" in HANDLERS
print("SMOKE_WF_OK", wf.raw.get("version"), len(wf.steps))

try:
    import faster_whisper

    print("SMOKE_WHISPER_OK", getattr(faster_whisper, "__version__", "?"))
except Exception as e:
    print("SMOKE_WHISPER_MISSING", e)
