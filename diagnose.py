#!/usr/bin/env python3
r"""Diagnostic test for the AI Video Reels Agent.

Checks the environment (Python, FFmpeg, project files), then runs a real
functional test of both scripts on tiny synthetic videos. Writes a
report to diagnostics/ and (by default) commits and pushes it to GitHub
so you can share it.

Run:  python diagnose.py          (test + upload)
      python diagnose.py --no-push  (test only, no upload)
"""

import argparse
import datetime
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT = []


def add(line: str = "") -> None:
    REPORT.append(line)
    print(line)


def check(name: str, ok: bool, detail: str = "") -> bool:
    add(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return ok


def run(cmd, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def ffmpeg_version() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        return ""
    result = run(["ffmpeg", "-version"])
    return (result.stdout or result.stderr).splitlines()[0]


def ffprobe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    try:
        return float(result.stdout.strip())
    except ValueError:
        return -1.0


def test_environment() -> bool:
    add("=== Environment ===")
    ok = True
    ok &= check("Python", True, f"{platform.python_version()} on {platform.system()}")
    ff = ffmpeg_version()
    ok &= check("FFmpeg in PATH", bool(ff), ff or "not found - run setup.ps1")
    ok &= check("ffprobe in PATH", bool(shutil.which("ffprobe")))
    required = ["setup.ps1", "remove_silence.py", "merge_videos.py",
                "make_reel.sh", "app.py", "diagnose.py"]
    for name in required:
        ok &= check(f"File {name}", (ROOT / name).is_file())
    return bool(ok)


def make_clip(dst: Path, duration: int, silence: str = "") -> bool:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=320x240:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
    ]
    if silence:
        cmd += ["-af", silence]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "libx264",
            "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(dst)]
    result = run(cmd)
    return result.returncode == 0


def test_remove_silence(tmp: Path) -> bool:
    add("\n=== Test: remove_silence.py ===")
    clip = tmp / "silence_test.mp4"
    if not check("create synthetic clip (4s tone + 3s silence)", make_clip(
            clip, 7, "volume=enable='between(t,4,7)':volume=0")):
        return False
    result = run([sys.executable, str(ROOT / "remove_silence.py"), str(clip)])
    if not check("script exits cleanly", result.returncode == 0,
                 (result.stderr or "").strip()[-300:]):
        add(result.stdout)
        return False
    out = clip.with_name("silence_test_tight.mp4")
    if not check("output file created", out.is_file()):
        return False
    duration = ffprobe_duration(out)
    expected = 7.0 - 3.0 + 0.3
    return check(f"output duration ~{expected:.1f}s", abs(duration - expected) < 0.6,
                 f"got {duration:.2f}s")


def test_merge(tmp: Path) -> bool:
    add("\n=== Test: merge_videos.py ===")
    clip1, clip2 = tmp / "m1.mp4", tmp / "m2.mp4"
    if not check("create synthetic clips (3s + 4s)", make_clip(clip1, 3) and make_clip(clip2, 4)):
        return False
    out = tmp / "merged.mp4"
    result = run([sys.executable, str(ROOT / "merge_videos.py"),
                  str(clip1), str(clip2), "-o", str(out), "--fade", "0.5"])
    if not check("script exits cleanly", result.returncode == 0,
                 (result.stderr or "").strip()[-300:]):
        add(result.stdout)
        return False
    duration = ffprobe_duration(out)
    return check("merged duration ~6.0s (3+4-2x0.5)",
                 abs(duration - 6.0) < 0.6, f"got {duration:.2f}s")


def probe_resolution(path: Path) -> str:
    result = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x", str(path),
    ])
    return result.stdout.strip()


def upload_report(report_path: Path) -> bool:
    add("\n=== Upload to GitHub ===")
    if run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT).returncode != 0:
        return check("git repository", False, "this folder is not a git repository")
    if not run(["git", "config", "user.email"], cwd=ROOT).stdout.strip():
        run(["git", "config", "user.name", "dhyani-sudo"], cwd=ROOT)
        run(["git", "config", "user.email", "dhyani-sudo@users.noreply.github.com"], cwd=ROOT)
    rel = str(report_path.relative_to(ROOT))
    run(["git", "add", rel], cwd=ROOT)
    commit = run(["git", "-c", "commit.gpgsign=false", "commit",
                  "-m", f"Diagnostic report {report_path.stem}"], cwd=ROOT)
    if commit.returncode != 0:
        add(commit.stderr.strip())
        return check("commit report", False)
    check("commit report", True, commit.stdout.strip().splitlines()[0] if commit.stdout else "")
    push = run(["git", "push"], cwd=ROOT)
    return check("push to GitHub", push.returncode == 0,
                 push.stderr.strip().splitlines()[-1] if push.stderr.strip() else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostics for the Reels Agent")
    parser.add_argument("--no-push", action="store_true",
                        help="do not upload the report to GitHub")
    args = parser.parse_args()

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    add(f"AI Video Reels Agent - diagnostic report {stamp}")

    env_ok = test_environment()
    with tempfile.TemporaryDirectory() as tmp:
        silence_ok = test_remove_silence(Path(tmp)) if env_ok else False
        merge_ok = test_merge(Path(tmp)) if env_ok else False
        if merge_ok:
            merged = Path(tmp) / "merged.mp4"
            add("\n=== Output specs ===")
            check("merged resolution 1080x1920", probe_resolution(merged) == "1080x1920",
                  probe_resolution(merged))

    add("\n=== Summary ===")
    all_ok = env_ok and silence_ok and merge_ok
    check("ALL TESTS PASSED", all_ok)

    report_dir = ROOT / "diagnostics"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"diag_{stamp}.txt"
    report_path.write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    add(f"\nReport saved to: {report_path}")

    if all_ok and not args.no_push:
        upload_report(report_path)
    elif not all_ok:
        add("\nReport NOT uploaded: fix the failing checks first, then rerun.")
    else:
        add("\n--no-push given: report stays local.")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
