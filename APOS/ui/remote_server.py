"""خادم ويب للجوال — راقب COS وأرسل أوامر من الهاتف."""
from __future__ import annotations

import json
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cos.remote import hub  # noqa: E402

HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"/>
<title>COS Remote</title>
<style>
body{font-family:Tahoma,sans-serif;background:#0f0f0f;color:#eee;margin:0;padding:12px}
h1{font-size:18px;margin:0 0 8px}
#status{padding:8px 10px;border-radius:8px;background:#1b2e1f;color:#8f8;margin-bottom:10px;font-size:14px}
#log{height:55vh;overflow:auto;background:#151515;border-radius:10px;padding:10px;margin-bottom:10px}
.msg{margin:8px 0;padding:8px 10px;border-radius:10px;max-width:92%;white-space:pre-wrap;word-break:break-word}
.user{background:#1e3a5f;margin-right:auto}
.bot{background:#222;margin-left:auto;color:#ddd}
.meta{font-size:11px;opacity:.6}
row{display:flex;gap:8px}
textarea{flex:1;min-height:64px;border-radius:10px;border:0;padding:10px;background:#1a1a1a;color:#fff;font-size:16px}
button{border:0;border-radius:10px;padding:12px 14px;font-size:15px;color:#fff}
#send{background:#1e88e5}#kill{background:#c62828}#ref{background:#455a64}
.hint{font-size:12px;opacity:.7;margin-top:8px}
</style>
</head>
<body>
<h1>COS على الهاتف</h1>
<div id="status">جاري الاتصال...</div>
<div id="log"></div>
<div style="display:flex;gap:8px;margin-bottom:8px">
  <button id="kill" onclick="doKill()">إيقاف</button>
  <button id="ref" onclick="refresh()">تحديث</button>
</div>
<div style="display:flex;gap:8px">
  <textarea id="q" placeholder="اكتب أمراً أو تكلم لاحقاً من اللابتوب..."></textarea>
  <button id="send" onclick="doSend()">إرسال</button>
</div>
<p class="hint">نفس شبكة الواي فاي مع اللابتوب. خارج البيت: استخدم Tailscale أو نفق آمن لاحقاً.</p>
<script>
async function refresh(){
  const r=await fetch('/api/status'); const d=await r.json();
  document.getElementById('status').textContent = d.status + (d.busy?' ⏳':'');
  const log=document.getElementById('log');
  log.innerHTML='';
  (d.messages||[]).forEach(m=>{
    const div=document.createElement('div');
    div.className='msg '+(m.role==='user'?'user':'bot');
    div.innerHTML='<div class="meta">'+m.at+' · '+m.role+'</div>'+m.text.replace(/</g,'&lt;');
    log.appendChild(div);
  });
  log.scrollTop=log.scrollHeight;
}
async function doSend(){
  const q=document.getElementById('q'); const t=q.value.trim(); if(!t) return;
  q.value='';
  await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal:t})});
  await refresh();
}
async function doKill(){
  await fetch('/api/kill',{method:'POST'}); await refresh();
}
setInterval(refresh, 2500); refresh();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self) -> None:
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._html()
            return
        if path == "/api/status":
            self._json(200, hub.snapshot())
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            data = {}
        if path == "/api/command":
            goal = str(data.get("goal") or "")
            # لا نعلّق طلب الهاتف أثناء المهام الطويلة
            import threading

            threading.Thread(
                target=hub.run_goal, args=(goal,), daemon=True, name="cos-phone-cmd"
            ).start()
            self._json(200, {"ok": True, "accepted": True, **hub.snapshot()})
            return
        if path == "/api/kill":
            self._json(200, {"ok": True, "reply": hub.kill(), **hub.snapshot()})
            return
        self._json(404, {"error": "not found"})


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    host = "0.0.0.0"
    port = 8787
    ip = local_ip()
    print("=" * 50)
    print(" COS Remote — للهاتف")
    print("=" * 50)
    print(f" على اللابتوب: http://127.0.0.1:{port}")
    print(f" على الهاتف (نفس الواي فاي): http://{ip}:{port}")
    print(" أوقف الخادم بـ Ctrl+C")
    print("=" * 50)
    hub.push("assistant", "لوحة الهاتف جاهزة. أرسل أوامرك من هنا.")
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nتوقف.")


if __name__ == "__main__":
    main()
