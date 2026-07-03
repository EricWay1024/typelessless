from __future__ import annotations

import html
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import history


def start(app) -> str:
    """Start the history web UI on localhost (ephemeral port); return its URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(app))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/"


def _make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console/log quiet
            pass

        def _send(self, code, body: bytes, ctype="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass

        def _redirect(self):
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

        def do_GET(self):
            path, _, query = self.path.partition("?")
            q = urllib.parse.parse_qs(query)
            if path == "/":
                self._send(200, _render(app).encode("utf-8"))
            elif path == "/audio":
                self._audio(q.get("id", [""])[0])
            else:
                self._send(404, b"not found")

        def do_POST(self):
            path, _, query = self.path.partition("?")
            eid = urllib.parse.parse_qs(query).get("id", [""])[0]
            try:
                if path == "/retry":
                    app.retry_entry(eid)
                elif path == "/copy":
                    app.copy_text(eid)
            except Exception:
                pass
            self._redirect()

        def _audio(self, eid):
            p = history.wav_path(history.get(eid))
            if not p:
                self._send(404, b"no audio")
                return
            try:
                self._send(200, p.read_bytes(), "audio/wav")
            except Exception:
                self._send(404, b"no audio")

    return Handler


def _render(app) -> str:
    cards = []
    for e in app.history_entries():
        status = e.get("status", "")
        color = {"ok": "#3ba55d", "failed": "#e05252", "processing": "#e0a52e"}.get(status, "#888")
        text = html.escape(e.get("text") or e.get("transcript") or "")
        err = html.escape(e.get("error") or "")
        eid = html.escape(e.get("id", ""))
        audio = f'<audio controls preload="none" src="/audio?id={eid}"></audio>' if e.get("wav") else '<span class="noaudio">audio pruned</span>'
        cards.append(
            f'<div class="card">'
            f'<div class="meta"><span class="badge" style="background:{color}">{html.escape(status)}</span>'
            f'<span>{html.escape(e.get("time", ""))}</span><span class="mode">{html.escape(e.get("mode", ""))}</span></div>'
            f'<div class="text">{text or "<i>(no text)</i>"}</div>'
            + (f'<div class="err">{err}</div>' if err else "")
            + f'<div class="row">{audio}'
            f'<form method="post" action="/retry?id={eid}"><button title="Re-transcribe the saved audio and copy the result">Retry</button></form>'
            f'<form method="post" action="/copy?id={eid}"><button>Copy</button></form>'
            f"</div></div>"
        )
    body = "\n".join(cards) or '<p class="empty">No dictations yet. Press your hotkey and speak.</p>'
    return _PAGE.replace("{{BODY}}", body)


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>typelessless — history</title>
<style>
  :root { color-scheme: dark light; }
  body { font: 15px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #16171b; color: #e6e6e6; }
  header { position: sticky; top: 0; background: #16171b; padding: 14px 20px; border-bottom: 1px solid #2a2c33; display: flex; gap: 16px; align-items: baseline; }
  h1 { font-size: 17px; margin: 0; }
  a.refresh { color: #6cc; text-decoration: none; }
  main { max-width: 820px; margin: 0 auto; padding: 16px 20px 60px; }
  .card { background: #1e2026; border: 1px solid #2a2c33; border-radius: 10px; padding: 12px 14px; margin: 12px 0; }
  .meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #9aa0aa; margin-bottom: 6px; }
  .badge { color: #fff; padding: 1px 8px; border-radius: 20px; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
  .mode { margin-left: auto; }
  .text { white-space: pre-wrap; word-break: break-word; }
  .err { color: #e08a8a; font-size: 12px; margin-top: 6px; }
  .row { display: flex; gap: 10px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
  .row form { margin: 0; }
  button { background: #2f3540; color: #e6e6e6; border: 1px solid #3a4150; border-radius: 7px; padding: 5px 12px; cursor: pointer; }
  button:hover { background: #39414e; }
  audio { height: 30px; }
  .noaudio, .empty { color: #777; font-size: 13px; }
</style></head>
<body>
  <header><h1>typelessless — history</h1><a class="refresh" href="/">↻ refresh</a></header>
  <main>{{BODY}}</main>
</body></html>"""
