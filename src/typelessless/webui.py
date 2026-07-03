from __future__ import annotations

import html
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import history


def start(app) -> str:
    """Start the history + settings web UI on localhost; return its URL."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(app))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}/"


def _make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
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

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _body(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            return self.rfile.read(n) if n else b""

        def do_GET(self):
            path, _, query = self.path.partition("?")
            q = urllib.parse.parse_qs(query)
            if path == "/":
                self._send(200, _render_history(app).encode("utf-8"))
            elif path == "/settings":
                self._send(200, _SETTINGS_PAGE.encode("utf-8"))
            elif path == "/api/settings":
                self._json(200, app.get_settings())
            elif path == "/audio":
                self._audio(q.get("id", [""])[0])
            else:
                self._send(404, b"not found")

        def do_POST(self):
            path, _, query = self.path.partition("?")
            if path == "/api/settings":
                try:
                    data = json.loads(self._body().decode("utf-8") or "{}")
                    self._json(200, app.save_settings(data))
                except Exception as exc:  # noqa: BLE001
                    self._json(400, {"error": str(exc)})
                return
            eid = urllib.parse.parse_qs(query).get("id", [""])[0]
            try:
                if path == "/retry":
                    app.retry_entry(eid)
                elif path == "/copy":
                    app.copy_text(eid)
            except Exception:
                pass
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

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


def _render_history(app) -> str:
    cards = []
    for e in app.history_entries():
        status = e.get("status", "")
        color = {"ok": "#3ba55d", "failed": "#e05252", "processing": "#e0a52e"}.get(status, "#888")
        text = html.escape(e.get("text") or e.get("transcript") or "")
        err = html.escape(e.get("error") or "")
        eid = html.escape(e.get("id", ""))
        audio = f'<audio controls preload="none" src="/audio?id={eid}"></audio>' if e.get("wav") else '<span class="noaudio">audio pruned</span>'
        cards.append(
            f'<div class="card"><div class="meta">'
            f'<span class="badge" style="background:{color}">{html.escape(status)}</span>'
            f'<span>{html.escape(e.get("time", ""))}</span><span class="mode">{html.escape(e.get("mode", ""))}</span></div>'
            f'<div class="text">{text or "<i>(no text)</i>"}</div>'
            + (f'<div class="err">{err}</div>' if err else "")
            + f'<div class="row">{audio}'
            f'<form method="post" action="/retry?id={eid}"><button>Retry</button></form>'
            f'<form method="post" action="/copy?id={eid}"><button>Copy</button></form>'
            f"</div></div>"
        )
    body = "\n".join(cards) or '<p class="empty">No dictations yet. Press your hotkey and speak.</p>'
    return _HISTORY_PAGE.replace("{{BODY}}", body)


_STYLE = """
  :root { color-scheme: dark light; }
  body { font: 15px/1.5 -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #16171b; color: #e6e6e6; }
  header { position: sticky; top: 0; background: #16171b; padding: 14px 20px; border-bottom: 1px solid #2a2c33; display: flex; gap: 16px; align-items: baseline; }
  h1 { font-size: 17px; margin: 0; } h2 { font-size: 14px; margin: 22px 0 8px; }
  header a, a.nav { color: #6cc; text-decoration: none; } header a.active { color: #e6e6e6; font-weight: 600; }
  main { max-width: 820px; margin: 0 auto; padding: 16px 20px 80px; }
  .card { background: #1e2026; border: 1px solid #2a2c33; border-radius: 10px; padding: 12px 14px; margin: 12px 0; }
  .meta { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #9aa0aa; margin-bottom: 6px; }
  .badge { color: #fff; padding: 1px 8px; border-radius: 20px; font-size: 11px; text-transform: uppercase; }
  .mode { margin-left: auto; }
  .text { white-space: pre-wrap; word-break: break-word; }
  .err { color: #e08a8a; font-size: 12px; margin-top: 6px; }
  .row { display: flex; gap: 10px; align-items: center; margin-top: 10px; flex-wrap: wrap; } .row form { margin: 0; }
  button { background: #2f3540; color: #e6e6e6; border: 1px solid #3a4150; border-radius: 7px; padding: 5px 12px; cursor: pointer; } button:hover { background: #39414e; }
  audio { height: 30px; } .noaudio, .empty, .hint { color: #777; font-size: 13px; }
  label { display: block; font-size: 12px; color: #9aa0aa; margin: 14px 0 4px; }
  textarea, input[type=text], select { width: 100%; box-sizing: border-box; background: #14151a; color: #e6e6e6; border: 1px solid #2a2c33; border-radius: 7px; padding: 8px; font: inherit; }
  textarea { resize: vertical; }
  .mode-box, .rule { background: #1e2026; border: 1px solid #2a2c33; border-radius: 10px; padding: 10px 12px; margin: 10px 0; }
  .rule { display: flex; gap: 8px; align-items: center; } .rule input { flex: 1; } .rule select { width: auto; }
  .savebar { position: fixed; bottom: 0; left: 0; right: 0; background: #14151a; border-top: 1px solid #2a2c33; padding: 12px 20px; display: flex; gap: 12px; align-items: center; }
  .primary { background: #2f6f4f; border-color: #3a8a63; }
"""

_HISTORY_PAGE = f"""<!doctype html><html><head><meta charset="utf-8"><title>typelessless — history</title>
<style>{_STYLE}</style></head><body>
<header><h1>typelessless</h1><a class="active" href="/">history</a><a href="/settings">settings</a>
<a class="nav" href="/" style="margin-left:auto">↻ refresh</a></header>
<main>{{{{BODY}}}}</main></body></html>"""

_SETTINGS_PAGE = f"""<!doctype html><html><head><meta charset="utf-8"><title>typelessless — settings</title>
<style>{_STYLE}</style></head><body>
<header><h1>typelessless</h1><a href="/">history</a><a class="active" href="/settings">settings</a></header>
<main>
  <label>Global prompt — personal info / rules prepended to every mode</label>
  <textarea id="global_prompt" rows="4"></textarea>

  <label>Vocabulary — one term per line (biases recognition + normalizes spelling)</label>
  <textarea id="vocab" rows="6"></textarea>

  <label>Default mode (used when no rule matches the focused app)</label>
  <select id="default_mode"></select>

  <h2>Modes <button onclick="addMode()">+ add mode</button></h2>
  <div id="modes"></div>

  <h2>Auto-select rules <button onclick="addRule()">+ add rule</button></h2>
  <p class="hint">On record start, the focused window's exe name and title are matched (case-insensitive substring). First match wins; otherwise the default mode.</p>
  <div id="rules"></div>
</main>
<div class="savebar"><button class="primary" onclick="save()">Save</button><span id="msg" class="hint"></span></div>
<script>
let S = null;
function esc(s){{ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
async function load(){{ S = await (await fetch('/api/settings')).json(); render(); }}
function render(){{
  document.getElementById('global_prompt').value = S.global_prompt || '';
  document.getElementById('vocab').value = (S.vocab||[]).join('\\n');
  renderModes(); renderDefault(); renderRules();
}}
function collectModes(){{ return [...document.querySelectorAll('#modes .nm')].map(x=>x.value.trim()).filter(Boolean); }}
function renderModes(){{
  const c = document.getElementById('modes'); c.innerHTML='';
  (S.modes||[]).forEach((m,i)=>{{
    const d = document.createElement('div'); d.className='mode-box';
    d.innerHTML = `<div class="row"><input class="nm" type="text" value="${{esc(m.name)}}" placeholder="mode name">
      <label style="margin:0"><input type="checkbox" class="llm" ${{m.use_llm!==false?'checked':''}}> LLM cleanup</label>
      <button onclick="delMode(${{i}})">delete</button></div>
      <textarea class="pr" rows="5" placeholder="system prompt for this mode">${{esc(m.prompt||'')}}</textarea>`;
    c.appendChild(d);
  }});
}}
function renderDefault(){{
  const s = document.getElementById('default_mode'); s.innerHTML='';
  collectModes().forEach(n=>{{ const o=document.createElement('option'); o.value=n; o.text=n; if(n===S.default_mode)o.selected=true; s.appendChild(o); }});
}}
function renderRules(){{
  const c = document.getElementById('rules'); c.innerHTML='';
  const modes = collectModes();
  (S.rules||[]).forEach((r,i)=>{{
    const opts = modes.map(n=>`<option ${{n===r.mode?'selected':''}}>${{esc(n)}}</option>`).join('');
    const d = document.createElement('div'); d.className='rule';
    d.innerHTML = `<input class="mt" type="text" value="${{esc(r.match||'')}}" placeholder="match (e.g. code, chrome, slack)"> → <select class="rm">${{opts}}</select> <button onclick="delRule(${{i}})">delete</button>`;
    c.appendChild(d);
  }});
}}
function gather(){{
  return {{
    global_prompt: document.getElementById('global_prompt').value,
    vocab: document.getElementById('vocab').value.split('\\n').map(s=>s.trim()).filter(Boolean),
    default_mode: document.getElementById('default_mode').value,
    modes: [...document.querySelectorAll('#modes .mode-box')].map(d=>({{name:d.querySelector('.nm').value.trim(), use_llm:d.querySelector('.llm').checked, prompt:d.querySelector('.pr').value}})),
    rules: [...document.querySelectorAll('#rules .rule')].map(d=>({{match:d.querySelector('.mt').value.trim(), mode:d.querySelector('.rm').value}})),
  }};
}}
function addMode(){{ S=gather(); S.modes.push({{name:'',prompt:'',use_llm:true}}); render(); }}
function delMode(i){{ S=gather(); S.modes.splice(i,1); render(); }}
function addRule(){{ S=gather(); S.rules.push({{match:'',mode:collectModes()[0]||''}}); render(); }}
function delRule(i){{ S=gather(); S.rules.splice(i,1); render(); }}
async function save(){{
  const r = await fetch('/api/settings', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(gather())}});
  if(r.ok){{ S = await r.json(); render(); msg('saved ✓'); }} else msg('save failed');
}}
function msg(t){{ const m=document.getElementById('msg'); m.textContent=t; setTimeout(()=>m.textContent='', 2500); }}
load();
</script></body></html>"""
