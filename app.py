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
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PORT = 8765

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


def list_files(folder: str) -> list:
    directory = ROOT / folder
    directory.mkdir(exist_ok=True)
    return sorted(
        p.name for p in directory.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )


def build_merge_cmd() -> list:
    patterns = [f"input/{pat}" for pat in GLOB_PATTERNS]
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return [sys.executable, "merge_videos.py", *patterns,
            "-o", f"output/reel_{stamp}.mp4"]


PAGE = """<!DOCTYPE html>
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
  <h2>Single video: remove silence</h2>
  <div id="inputList"><span class="muted">Loading...</span></div>
  <div class="muted">Put videos in the <b>input</b> folder, then refresh this page.</div>
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
            snapshot["input_files"] = list_files("input")
            snapshot["output_files"] = list_files("output")
            self._send(200, json.dumps(snapshot))
        elif path == "/open/output":
            folder = ROOT / "output"
            folder.mkdir(exist_ok=True)
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
        if urlparse(self.path).path != "/api/run":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, json.dumps({"ok": False, "error": "bad request"}))

        action = payload.get("action", "")
        if action == "silence":
            name = Path(payload.get("file", "")).name
            target = ROOT / "input" / name
            if not name or not target.is_file():
                return self._send(400, json.dumps({"ok": False, "error": "file not found in input/"}))
            ok, error = start_job(f"Remove silence: {name}",
                                  [sys.executable, "remove_silence.py", str(target)])
        elif action == "merge":
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
