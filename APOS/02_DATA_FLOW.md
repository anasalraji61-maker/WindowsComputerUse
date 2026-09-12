# APOS v1.1 — Data Flow (تعلّم + إدراك)

---

## التدفق المعرفي

```mermaid
flowchart TB
  U[أمر المستخدم] --> G[Goal]
  G --> PLAN[Plan / Workflow step]
  PLAN --> WS[World State]
  WS --> DEC{Decision}

  DEC -->|خبرة سابقة كافية| ACT[Execute]
  DEC -->|مجهول / ثقة منخفضة| EXP[Exploration Mode]
  EXP --> OBS[Observe: نافذة + لقطة عند حدث]
  OBS --> UND[Understand: OCR / UI hints]
  UND --> HYP[فرضية إجراء]
  HYP --> ACT

  ACT --> SUP[Supervisor + Confidence]
  SUP -->|رفض| U
  SUP -->|موافق| HAND[Mouse/Keyboard/Files]
  HAND --> ENV[المنصة على الشاشة]
  ENV --> VER[Verify عبر Perception]
  VER -->|نجاح| LEARN[Reflect + اكتب Experience]
  VER -->|فشل| DEC
  LEARN --> STORE[Experience Store]
  STORE --> WS
```

---

## متى تُلتقط الشاشة؟

```mermaid
flowchart LR
  A[حدث نافذة/حوار/ملف] --> S[لقطة]
  B[Exploration يحتاج فهم] --> S
  C[Verify بعد إجراء مهم] --> S
  D[لا حدث] --> N[لا لقطة]
```

---

## Experience Record (مثال شكل البيانات)

```json
{
  "platform_hint": "strategyquant",
  "window_title_pattern": "StrategyQuant",
  "tried": [
    {"action": "click_text:Start", "result": "fail", "note": "no change"},
    {"action": "click_text:Run", "result": "success", "note": "progress bar appeared"}
  ],
  "best": {"action": "click_text:Run", "confidence": 0.82},
  "updated_at": "ISO-8601"
}
```

النظام يكتب هذا — المستخدم لا يملأ إحداثيات مسبقاً.
