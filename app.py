#!/usr/bin/env python3
r"""Simple local web interface for the AI Video Reels Agent.

Run on your PC:   python app.py
(or double-click  start_app.bat)

A page opens automatically at http://localhost:8765 where you can:
- remove silence from a single video in input/
- merge ALL videos in input/ into one reel
- run the diagnostic test
- watch the live log and see the results

The server runs only on your own computer (localhost) - nothing is
exposed to the network.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PORT = 8765
CONFIG_PATH = ROOT / "config.json"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
GLOB_PATTERNS = ["*.mp4", "*.MP4", "*.mov", "*.MOV", "*.mkv", "*.webm", "*.avi"]

_lock = threading.Lock()
_state = {"running": False, "title": "", "log": [], "returncode": None}


def log(line: str) -> None:
    with _lock:
        _state["log"].append(line.rstrip("\n"))


def start_job(title: str, cmd: list) -> tuple:
    with _lock:
        if _state["running"]:
            return False, "Another task is already running - wait for it to finish."
        _state.update(running=True, title=title, log=[], returncode=None)

    log(f">>> {title}")

    def worker():
        code = 1
        try:
            proc = subprocess.Popen(
                cmd, cwd=str(ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            for line in proc.stdout:
                log(line)
            code = proc.wait()
        except Exception as exc:
            log(f"ERROR: {exc}")
        with _lock:
            _state["running"] = False
            _state["returncode"] = code
        log(f"<<< Finished (exit code {code})")

    threading.Thread(target=worker, daemon=True).start()
    return True, ""


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", path.name)]


def get_config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _resolve_folder(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def get_input_dir() -> Path:
    path = _resolve_folder(get_config().get("input_dir", "input"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_output_dir() -> Path:
    path = _resolve_folder(get_config().get("output_dir", "output"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def set_dir(key: str, value: str) -> tuple:
    path = _resolve_folder(value)
    if not path.is_dir():
        if key == "output_dir":
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return False, f"Could not create folder: {exc}"
        else:
            return False, f"Folder does not exist: {path}"
    config = get_config()
    config[key] = str(path)
    recent = [p for p in config.get("recent_dirs", []) if p != str(path)]
    recent.insert(0, str(path))
    config["recent_dirs"] = recent[:10]
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return True, str(path)


def list_video_names() -> list:
    input_dir = get_input_dir()
    return sorted(
        (p.name for p in input_dir.iterdir()
         if p.is_file() and not p.name.startswith(".")),
        key=lambda n: [int(t) if t.isdigit() else t.lower()
                       for t in re.split(r"(\d+)", n)],
    )


def build_merge_cmd() -> list:
    input_dir = get_input_dir()
    files = sorted(
        (p for p in input_dir.iterdir()
         if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
         and not p.name.startswith(".")),
        key=natural_key,
    )
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = get_output_dir() / f"reel_{stamp}.mp4"
    return [sys.executable, "merge_videos.py", *[str(p) for p in files], "-o", str(out)]


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reels Agent</title>
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #10141c; color: #e8eaf0;
         max-width: 860px; margin: 0 auto; padding: 24px; }
  h1 { font-size: 22px; } h2 { font-size: 16px; margin-top: 28px; color: #9fb3d1; }
  button { background: #3b6ef5; color: white; border: 0; border-radius: 6px;
           padding: 8px 14px; margin: 3px; cursor: pointer; font-size: 14px; }
  button:hover { background: #2f5ad0; }
  button:disabled { background: #444c5c; cursor: not-allowed; }
  button.small { padding: 4px 10px; font-size: 12px; }
  .card { background: #1a2130; border-radius: 10px; padding: 16px; margin: 12px 0; }
  #log { background: #0b0e14; color: #9fe8a8; padding: 12px; border-radius: 8px;
         white-space: pre-wrap; font-family: Consolas, monospace; font-size: 12px;
         max-height: 300px; overflow-y: auto; }
  .file { display: flex; justify-content: space-between; align-items: center;
          padding: 4px 0; border-bottom: 1px solid #26304a; }
  .muted { color: #8a94a8; font-size: 13px; }
  .status { font-weight: bold; }
  .ok { color: #58d68d; } .bad { color: #ec7063; } .busy { color: #f5b041; }
</style>
</head>
<body>
<h1>AI Video Reels Agent</h1>

<div class="card">
  <h2>Make a reel (merge ALL clips in input/)</h2>
  <button id="mergeBtn" onclick="run('merge')">Merge all clips</button>
  <button id="diagBtn" onclick="run('diagnose')">Run diagnostics</button>
  <span class="muted">Clips are merged in alphabetical order, 0.5s crossfade, 1080x1920.</span>
</div>

<div class="card">
  <h2>Folders</h2>
  <div class="file"><span><b>Input</b> (your clips)</span></div>
  <input id="inputDir" style="width:70%; padding:6px; border-radius:6px; border:1px solid #2c3a55; background:#0b0e14; color:#e8eaf0;">
  <button onclick="setDir('input_dir','inputDir')">Set input folder</button>
  <select id="inputRecent" onchange="pickRecent('input_dir','inputDir',this)"></select>
  <div class="file" style="margin-top:10px;"><span><b>Output</b> (finished reels)</span></div>
  <input id="outputDir" style="width:70%; padding:6px; border-radius:6px; border:1px solid #2c3a55; background:#0b0e14; color:#e8eaf0;">
  <button onclick="setDir('output_dir','outputDir')">Set output folder</button>
  <select id="outputRecent" onchange="pickRecent('output_dir','outputDir',this)"></select>
  <div class="muted">Type a folder path (e.g. C:\Users\evile\Videos) or pick a recent one. Choices are saved on your PC.</div>
</div>

<div class="card">
  <h2>Single video: remove silence</h2>
  <div id="inputList"><span class="muted">Loading...</span></div>
  <div class="muted">Videos from the input folder above appear here. Refresh the page after adding files.</div>
</div>

<div class="card">
  <h2>Results in output/</h2>
  <div id="outputList"><span class="muted">Loading...</span></div>
  <button onclick="fetch('/open/output').then(refresh)">Open output folder</button>
</div>

<div class="card">
  <h2>Log <span id="status" class="status"></span></h2>
  <div id="log">Idle. Pick an action above.</div>
</div>

<script>
let busy = false;

async function refresh() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    busy = s.running;
    const st = document.getElementById('status');
    if (s.running) { st.textContent = '- RUNNING: ' + s.title; st.className = 'status busy'; }
    else if (s.returncode === 0) { st.textContent = '- ready'; st.className = 'status ok'; }
    else if (s.returncode !== null) { st.textContent = '- last task FAILED (see log)'; st.className = 'status bad'; }
    else { st.textContent = ''; st.className = 'status'; }

    document.getElementById('log').textContent = s.log.length ? s.log.join('\\n') : 'Idle.';
    const logs = document.getElementById('log');
    logs.scrollTop = logs.scrollHeight;

    if (document.activeElement !== document.getElementById('inputDir'))
      document.getElementById('inputDir').value = s.input_dir;
    if (document.activeElement !== document.getElementById('outputDir'))
      document.getElementById('outputDir').value = s.output_dir;

    const recent = s.recent_dirs || [];
    for (const [selId, current] of [['inputRecent', s.input_dir], ['outputRecent', s.output_dir]]) {
      const sel = document.getElementById(selId);
      const wanted = JSON.stringify(recent);
      if (sel.dataset.sig !== wanted) {
        sel.dataset.sig = wanted;
        sel.innerHTML = '<option value="">Recent folders...</option>' +
          recent.map(p => `<option value="${p}">${p}</option>`).join('');
      }
      sel.value = '';
    }

    const inList = document.getElementById('inputList');
    inList.innerHTML = s.input_files.length
      ? s.input_files.map(f =>
          `<div class="file"><span>${f}</span><span>` +
          `<button class="small" onclick="run('silence','${f}')">Remove silence</button>` +
          `</span></div>`).join('')
      : '<span class="muted">input/ is empty.</span>';

    const outList = document.getElementById('outputList');
    outList.innerHTML = s.output_files.length
      ? s.output_files.map(f => `<div class="file"><span>${f}</span></div>`).join('')
      : '<span class="muted">Nothing yet.</span>';

    document.getElementById('mergeBtn').disabled = busy;
    document.getElementById('diagBtn').disabled = busy;
    document.querySelectorAll('#inputList button').forEach(b => b.disabled = busy);
  } catch (e) { /* server restarting */ }
}

async function setDir(key, fieldId) {
  const value = document.getElementById(fieldId).value.trim();
  if (!value) return;
  const r = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({key: key, value: value})
  });
  const j = await r.json();
  if (!j.ok) alert('Could not set folder: ' + j.error);
  refresh();
}

async function pickRecent(key, fieldId, sel) {
  if (!sel.value) return;
  document.getElementById(fieldId).value = sel.value;
  await setDir(key, fieldId);
}

async function run(action, file) {
  const r = await fetch('/api/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: action, file: file})
  });
  const j = await r.json();
  if (!j.ok) alert(j.error);
  refresh();
}

setInterval(refresh, 1500);
refresh();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "application/json; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/status":
            with _lock:
                snapshot = {**_state, "log": list(_state["log"])}
            snapshot["input_dir"] = str(get_input_dir())
            snapshot["input_files"] = list_video_names()
            out_dir = get_output_dir()
            snapshot["output_dir"] = str(out_dir)
            snapshot["output_files"] = sorted(
                p.name for p in out_dir.iterdir()
                if p.is_file() and not p.name.startswith(".")
            )
            snapshot["recent_dirs"] = get_config().get("recent_dirs", [])
            self._send(200, json.dumps(snapshot))
        elif path == "/api/config":
            self._send(200, json.dumps({
                "input_dir": str(get_input_dir()),
                "output_dir": str(get_output_dir()),
                "recent_dirs": get_config().get("recent_dirs", []),
            }))
        elif path == "/open/output":
            folder = get_output_dir()
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(folder))
                    self._send(200, json.dumps({"ok": True}))
                else:
                    subprocess.Popen(["xdg-open", str(folder)])
                    self._send(200, json.dumps({"ok": True}))
            except Exception:
                self._send(200, json.dumps({
                    "ok": False, "error": f"Open it manually: {folder}"
                }))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/run", "/api/config"):
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, json.dumps({"ok": False, "error": "bad request"}))

        if path == "/api/config":
            key = payload.get("key", "")
            value = payload.get("value", "").strip()
            if key not in ("input_dir", "output_dir") or not value:
                return self._send(400, json.dumps({"ok": False, "error": "bad request"}))
            ok, message = set_dir(key, value)
            return self._send(200, json.dumps({"ok": ok, "error": message}))

        action = payload.get("action", "")
        if action == "silence":
            name = Path(payload.get("file", "")).name
            target = get_input_dir() / name
            if not name or not target.is_file():
                return self._send(400, json.dumps({"ok": False, "error": "file not found in the input folder"}))
            ok, error = start_job(f"Remove silence: {name}",
                                  [sys.executable, "remove_silence.py", str(target)])
        elif action == "merge":
            if not list_video_names():
                return self._send(400, json.dumps({"ok": False,
                    "error": "the input folder contains no videos"}))
            ok, error = start_job("Merge all clips", build_merge_cmd())
        elif action == "diagnose":
            ok, error = start_job("Diagnostics", [sys.executable, "diagnose.py"])
        else:
            return self._send(400, json.dumps({"ok": False, "error": "unknown action"}))
        self._send(200, json.dumps({"ok": ok, "error": error}))


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    print(f"Interface running at http://localhost:{PORT}  (Ctrl+C to stop)")
    print("Keep this window open while you use the app.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
