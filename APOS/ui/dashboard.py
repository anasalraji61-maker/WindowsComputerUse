"""لوحة مراقبة المنظومة — حالة الخدمات + أهداف + مقاييس."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tkinter as tk
from tkinter import font as tkfont, scrolledtext

from cos.data import get_data_layer
from cos.plugins import REGISTRY
from cos.runtime import RUNTIME


class Dashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("COS Dashboard")
        self.root.configure(bg="#101418")
        self.root.geometry("720x560+40+40")
        self.font = tkfont.Font(family="Consolas", size=10)
        self.title_font = tkfont.Font(family="Tahoma", size=12, weight="bold")

        top = tk.Frame(self.root, bg="#101418")
        top.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(
            top, text="COS Command Center", bg="#101418", fg="#80cbc4", font=self.title_font
        ).pack(side=tk.LEFT)
        tk.Button(
            top, text="تحديث", command=self.refresh, bg="#264653", fg="white", relief=tk.FLAT
        ).pack(side=tk.RIGHT, padx=4)
        tk.Button(
            top, text="إيقاف طارئ", command=self.kill, bg="#c62828", fg="white", relief=tk.FLAT
        ).pack(side=tk.RIGHT, padx=4)

        self.text = scrolledtext.ScrolledText(
            self.root, bg="#0b0f12", fg="#dce7ea", insertbackground="white", font=self.font
        )
        self.text.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.root.after(500, self.refresh)
        self.root.after(5000, self._auto)

    def kill(self) -> None:
        RUNTIME.kill()
        self.refresh()

    def _auto(self) -> None:
        self.refresh()
        self.root.after(5000, self._auto)

    def refresh(self) -> None:
        def work():
            try:
                layer = get_data_layer()
                st = layer.status()
                goals = layer.sql.recent_goals(12)
                plugs = REGISTRY.catalog()
                rate = layer.sql.success_rate()
                lines = [
                    f"busy={RUNTIME.busy} killed={RUNTIME.killed}",
                    f"success_rate={rate:.2%}",
                    "",
                    "=== Data Layer ===",
                    f"SQL: {st['sql']}",
                    f"Redis: {st['redis']}",
                    f"Vector: {st['vector']}",
                    f"System: {st['system']}",
                    "",
                    "=== Learning (7d) ===",
                ]
                try:
                    from cos.memory.learning_report import build_learning_report
                    from cos.core.goals import GoalManager
                    from cos.core.scheduler import Scheduler
                    from cos.perception.world_model import get_world_model
                    from cos.core.priority import ProjectManager

                    rep = build_learning_report("هذا الأسبوع", save=False)
                    lines.append(
                        f"attempts={rep.total} ok={rep.successes} fail={rep.failures} rate={rep.success_rate:.0%}"
                    )
                    lines.append(f"recoveries≈{rep.recovery_count} goals_logged={rep.goals_count}")
                    lines.append("")
                    lines.append("=== Goals / Projects / Schedule / World ===")
                    lines.append(GoalManager().summary())
                    lines.append(ProjectManager().summary())
                    lines.append(Scheduler().summary())
                    lines.append(get_world_model().summary())
                    try:
                        from cos.brain import status_text

                        lines.append("")
                        lines.append(status_text())
                    except Exception:
                        pass
                except Exception as e:
                    lines.append(f"learning: {e}")
                lines.append("")
                lines.append("=== Plugins ===")
                for cat, ids in sorted(plugs.items()):
                    lines.append(f"{cat}: {', '.join(ids)}")
                lines.append("")
                lines.append("=== Recent Goals ===")
                for g in goals:
                    lines.append(
                        f"{g.get('created_at','')} [{g.get('route')}] {g.get('status')} | {(g.get('goal') or '')[:80]}"
                    )
                body = "\n".join(lines)
            except Exception as e:
                body = f"Dashboard error: {e}"
            self.root.after(0, lambda: self._set(body))

        threading.Thread(target=work, daemon=True).start()

    def _set(self, body: str) -> None:
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, body)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    Dashboard().run()


if __name__ == "__main__":
    main()
