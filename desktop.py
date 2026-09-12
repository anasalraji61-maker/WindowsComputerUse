"""
تحكم فعلي بماوس ولوحة مفاتيح ويندوز عبر PyAutoGUI + لقطات شاشة.
"""
from __future__ import annotations

import base64
import ctypes
import io
import time
from dataclasses import dataclass

import mss
import pyautogui
from PIL import Image

# DPI على ويندوز — بدونه النقرات تطيح في أماكن خاطئة أحياناً
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01  # أسرع ما أمكن


@dataclass
class ScreenMap:
    real_w: int
    real_h: int
    model_w: int
    model_h: int

    def to_real(self, x: int, y: int) -> tuple[int, int]:
        rx = int(x * self.real_w / self.model_w)
        ry = int(y * self.real_h / self.model_h)
        return max(0, min(rx, self.real_w - 1)), max(0, min(ry, self.real_h - 1))


def get_screen_map(model_w: int | None = None, model_h: int | None = None) -> ScreenMap:
    # أصغر = أرخص توكنات رؤية + أسرع. الافتراضي 768x480
    import os

    if model_w is None:
        try:
            model_w = int(os.getenv("SCREEN_MODEL_W", "768"))
        except ValueError:
            model_w = 768
    if model_h is None:
        try:
            model_h = int(os.getenv("SCREEN_MODEL_H", "480"))
        except ValueError:
            model_h = 480
    model_w = max(512, min(int(model_w), 1280))
    model_h = max(320, min(int(model_h), 800))
    size = pyautogui.size()
    return ScreenMap(int(size.width), int(size.height), model_w, model_h)


def take_screenshot_b64(screen: ScreenMap) -> tuple[str, str]:
    """يرجع (base64, media_type). JPEG مضغوط لتقليل التكلفة."""
    import os

    try:
        quality = int(os.getenv("SCREEN_JPEG_QUALITY", "40"))
    except ValueError:
        quality = 40
    quality = max(25, min(quality, 70))

    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        if img.size != (screen.real_w, screen.real_h):
            img = img.resize((screen.real_w, screen.real_h), Image.Resampling.BILINEAR)
        img = img.resize((screen.model_w, screen.model_h), Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return base64.standard_b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def _key_map(key: str) -> str:
    k = key.strip().lower()
    aliases = {
        "return": "enter",
        "enter": "enter",
        "esc": "escape",
        "escape": "escape",
        "super": "win",
        "meta": "win",
        "cmd": "win",
        "control": "ctrl",
        "page_down": "pagedown",
        "page_up": "pageup",
        "space": "space",
    }
    return aliases.get(k, k)


def execute_action(action_input: dict, screen: ScreenMap) -> str:
    action = action_input.get("action")
    if not action:
        return "error: missing action"

    try:
        if action == "screenshot":
            return "ok: screenshot"

        if action == "mouse_move":
            x, y = action_input["coordinate"]
            rx, ry = screen.to_real(int(x), int(y))
            pyautogui.moveTo(rx, ry, duration=0)
            return f"ok: move {rx},{ry}"

        if action == "left_click":
            if "coordinate" in action_input and action_input["coordinate"] is not None:
                x, y = action_input["coordinate"]
                rx, ry = screen.to_real(int(x), int(y))
                # حركة ظاهرة ثم نقر فوري
                pyautogui.moveTo(rx, ry, duration=0)
                pyautogui.click(rx, ry)
                return f"ok: left_click {rx},{ry}"
            pyautogui.click()
            return "ok: left_click"

        if action == "right_click":
            if "coordinate" in action_input and action_input["coordinate"] is not None:
                x, y = action_input["coordinate"]
                rx, ry = screen.to_real(int(x), int(y))
                pyautogui.moveTo(rx, ry, duration=0)
                pyautogui.rightClick(rx, ry)
                return f"ok: right_click {rx},{ry}"
            pyautogui.rightClick()
            return "ok: right_click"

        if action == "double_click":
            if "coordinate" in action_input and action_input["coordinate"] is not None:
                x, y = action_input["coordinate"]
                rx, ry = screen.to_real(int(x), int(y))
                pyautogui.moveTo(rx, ry, duration=0)
                pyautogui.doubleClick(rx, ry)
                return f"ok: double_click {rx},{ry}"
            pyautogui.doubleClick()
            return "ok: double_click"

        if action == "middle_click":
            if "coordinate" in action_input and action_input["coordinate"] is not None:
                x, y = action_input["coordinate"]
                rx, ry = screen.to_real(int(x), int(y))
                pyautogui.moveTo(rx, ry, duration=0)
                pyautogui.middleClick(rx, ry)
                return f"ok: middle_click {rx},{ry}"
            pyautogui.middleClick()
            return "ok: middle_click"

        if action == "left_click_drag":
            sx, sy = action_input.get("start_coordinate") or action_input["coordinate"]
            ex, ey = action_input["coordinate"]
            rsx, rsy = screen.to_real(int(sx), int(sy))
            rex, rey = screen.to_real(int(ex), int(ey))
            pyautogui.moveTo(rsx, rsy, duration=0)
            pyautogui.dragTo(rex, rey, duration=0.12, button="left")
            return f"ok: drag {rsx},{rsy}->{rex},{rey}"

        if action == "type":
            text = action_input.get("text") or ""
            low = text.strip().lower()
            # أمان برمجي: لا تكتب أوامر تفتح Docker/Notepad بالتخمين
            if low in ("docker", "docker desktop", "notepad", "notepad.exe"):
                return f"skipped: blocked auto-launch '{text}' (safety)"
            if any(ord(c) > 127 for c in text) or len(text) > 40:
                import pyperclip

                old = None
                try:
                    old = pyperclip.paste()
                except Exception:
                    pass
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.05)
                if old is not None:
                    try:
                        pyperclip.copy(old)
                    except Exception:
                        pass
            else:
                pyautogui.write(text, interval=0)
            return f"ok: typed {len(text)} chars"

        if action == "key":
            raw = action_input.get("text") or action_input.get("key") or ""
            parts = [_key_map(p) for p in raw.replace("+", " ").split() if p]
            if not parts:
                return "error: empty key"
            # لا تستخدم Win وحدها لفتح البحث إلا بطلب صريح
            if parts == ["win"]:
                return "skipped: bare Win key blocked (opens search)."
            # منع اختصارات خطرة شائعة
            joined = "+".join(parts)
            if joined in ("ctrl+shift+escape",):  # نادر لكن لا نفتح مدير المهام تلقائياً
                pass
            if len(parts) == 1:
                pyautogui.press(parts[0])
            else:
                pyautogui.hotkey(*parts)
            return f"ok: key {raw}"

        if action == "scroll":
            direction = (action_input.get("scroll_direction") or "down").lower()
            amount = int(action_input.get("scroll_amount") or 3)
            if "coordinate" in action_input and action_input["coordinate"] is not None:
                x, y = action_input["coordinate"]
                rx, ry = screen.to_real(int(x), int(y))
                pyautogui.moveTo(rx, ry, duration=0)
            clicks = amount * 120
            if direction == "up":
                pyautogui.scroll(clicks)
            elif direction == "down":
                pyautogui.scroll(-clicks)
            elif direction == "left":
                pyautogui.hscroll(-clicks)
            else:
                pyautogui.hscroll(clicks)
            return f"ok: scroll {direction} {amount}"

        if action in ("wait", "hold_key"):
            duration = float(action_input.get("duration") or 0.2)
            time.sleep(min(duration, 0.4))  # سقف قصير — لا حلقات انتظار
            return f"ok: wait {min(duration, 0.4)}s"

        if action in ("left_mouse_down", "left_mouse_up"):
            if action.endswith("down"):
                pyautogui.mouseDown()
            else:
                pyautogui.mouseUp()
            return f"ok: {action}"

        return f"error: unsupported action {action}"
    except pyautogui.FailSafeException:
        raise
    except Exception as e:
        return f"error: {e}"
