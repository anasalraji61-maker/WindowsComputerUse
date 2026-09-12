"""قناة تعاون مع Cursor عبر ملفات — بلا نقر على واجهة الدردشة."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cos.core.task_manager import TaskState, TaskStore


def write_task_for_cursor(*, store: "TaskStore", goal: str, context: dict[str, Any]) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    facts = context.get("facts") or context
    facts_txt = json.dumps(facts, ensure_ascii=False, indent=2)[:3500]
    body = f"""# طلب إلى Cursor — من مدير مهام COS

**الوقت:** {stamp}

## الهدف من المستخدم
{goal}

## حقائق محلية جمعها النظام
```json
{facts_txt}
```

## المطلوب منك (Cursor)
1. اقرأ الهدف والحقائق أعلاه.
2. نفّذ التعديلات/التحليل داخل المشروع فقط حسب المطلوب.
3. شغّل أي اختبارات مناسبة إن وُجدت.
4. اكتب ردك في الملف:
   `{store.cursor_reply}`
   بالقالب التالي:

```markdown
# رد Cursor
## ما تم
- ...
## الملفات التي تغيّرت
- ...
## نتائج الاختبارات
- ...
## ما يحتاج قرار المستخدم
- ...
```

## قواعد
- لا تدّعِ النجاح بدون أدلة (مسارات ملفات / مخرجات اختبار).
- لا تنفّذ حذفاً واسعاً أو دفعاً أو تداولاً حياً.
- إن نقصت معلومة: اكتبها تحت «ما يحتاج قرار المستخدم».
"""
    store.task_md.write_text(body, encoding="utf-8")
    # أيضاً HANDOFF قديم للتوافق
    try:
        handoff = store.root.parent / "HANDOFF_FOR_AGENT.md"
        handoff.write_text(
            f"# HANDOFF\n\nانظر أيضاً: `{store.task_md}`\n\n## المهمة الحالية\n{goal}\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    return store.task_md


def read_cursor_reply(store: "TaskStore") -> str:
    p = store.cursor_reply
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) < 40:
        return ""
    # تجاهل القالب الفارغ
    if "(اكتب هنا" in text or text.count("- ...") >= 2:
        return ""
    if "ما تم" in text and len(text) < 160 and text.count("\n-") <= 4:
        # غالباً هيكل بلا محتوى حقيقي
        body = text.split("## ما تم", 1)[-1]
        if "اكتب" in body or body.strip().startswith("-"):
            meaningful = [
                ln
                for ln in body.splitlines()
                if ln.strip() and not ln.strip().startswith("#") and ln.strip() not in ("-", "- ")
            ]
            if len(" ".join(meaningful)) < 30:
                return ""
    return text


def write_final_report(store: "TaskStore", state: "TaskState") -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# تقرير مدير المهام COS",
        "",
        f"**الوقت:** {stamp}",
        f"**معرّف المهمة:** `{state.id}`",
        f"**الحالة:** `{state.phase}`",
        "",
        "## الهدف",
        state.goal,
        "",
        "## المراحل",
    ]
    for s in state.stages:
        lines.append(f"- **{s.title}** — `{s.status}`")
        if s.detail:
            lines.append(f"  - {s.detail}")

    lines.extend(["", "## أدلة / نتائج"])
    for key in ("analyze", "files", "git", "tests", "qc", "cursor_reply"):
        if key not in state.results:
            continue
        lines.append(f"### {key}")
        val = state.results[key]
        if isinstance(val, str):
            lines.append(val[:3000])
        else:
            lines.append("```json")
            lines.append(json.dumps(val, ensure_ascii=False, indent=2)[:4000])
            lines.append("```")
        lines.append("")

    if state.needs_human:
        lines.extend(["## يحتاج قرار/تدخل منك", state.needs_human, ""])

    lines.extend(
        [
            "## ملفات التعاون",
            f"- STATUS: `{store.status_path}`",
            f"- TASK: `{store.task_md}`",
            f"- CURSOR_REPLY: `{store.cursor_reply}`",
            "",
            "## الخلاصة",
            (
                "اكتملت الدورة مع أدلة موثّقة."
                if state.phase == "done"
                else "الدورة توقفت بانتظار تدخل أو معلومات ناقصة — انظر القسم أعلاه."
            ),
        ]
    )
    store.report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # نسخة ظاهرة للجذر
    try:
        (store.root.parent / "REPORT_FOR_CURSOR.md").write_text(
            store.report_md.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    except Exception:
        pass
    return store.report_md
