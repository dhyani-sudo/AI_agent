#!/usr/bin/env python3
r"""Merge multiple videos into one vertical reel (1080x1920).

Every clip is normalized to the same resolution, frame rate, and audio
format, then joined. A short crossfade transition is added between clips
(disable with --fade 0).

Usage:
    python merge_videos.py input\clip1.mp4 input\clip2.mp4
    python merge_videos.py input\*.mp4 -o output\reel.mp4
    python merge_videos.py clip1.mp4 clip2.mp4 clip3.mp4 --fade 0.5 --fit crop
"""

import argparse
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def require_ffmpeg() -> None:
    from shutil import which
    if not which("ffmpeg") or not which("ffprobe"):
        die(
            "FFmpeg/ffprobe not found. Run setup.ps1 first, or install FFmpeg "
            "and make sure 'ffmpeg -version' works in PowerShell."
        )


def run(cmd) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        die("FFmpeg failed:\n" + (result.stderr or "").strip()[-2000:])


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        die(f"Could not read duration of {path}. Not a valid video?")


def probe_has_audio(path: Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(path),
        ],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def normalize(src: Path, dst: Path, width: int, height: int, fps: int, fit: str) -> None:
    if fit == "crop":
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )
    else:
        video_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        )

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
    ]
    if probe_has_audio(src):
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-map", "0:v:0", "-map", "1:a", "-shortest"]
    cmd += [
        "-vf", video_filter,
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(dst),
    ]
    run(cmd)


def merge_with_fades(parts, out: Path, fade: float) -> None:
    durations = [probe_duration(p) for p in parts]
    n = len(parts)

    if n == 1 or fade <= 0:
        list_file = out.parent / (out.stem + "_concat.txt")
        list_file.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts),
            encoding="utf-8",
        )
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-movflags", "+faststart", str(out),
        ])
        list_file.unlink(missing_ok=True)
        return

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for p in parts:
        cmd += ["-i", str(p)]

    chains = []
    total = durations[0]
    v_prev, a_prev = "[0:v]", "[0:a]"
    for i in range(1, n):
        offset = total - fade
        if offset <= 0:
            die(f"Crossfade ({fade}s) is longer than the material so far "
                f"({total:.1f}s). Use a shorter --fade.")
        v_out = f"[v{i}]" if i < n - 1 else "[vout]"
        a_out = f"[a{i}]" if i < n - 1 else "[aout]"
        chains.append(
            f"{v_prev}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}{v_out};"
            f"{a_prev}[{i}:a]acrossfade=d={fade}:c1=tri:c2=tri{a_out}"
        )
        total = total + durations[i] - fade
        v_prev, a_prev = v_out, a_out

    cmd += ["-filter_complex", ";".join(chains)]
    cmd += [
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    run(cmd)
    print(f"Joined {n} clips with {n - 1} crossfade(s) of {fade}s.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge multiple videos into one vertical reel."
    )
    parser.add_argument("inputs", nargs="+",
                        help="Video files to merge, in order")
    parser.add_argument("-o", "--output", default="output/reel.mp4",
                        help="Output path (default: output/reel.mp4)")
    parser.add_argument("--fade", type=float, default=0.5,
                        help="Crossfade duration in seconds (0 = hard cut, default: 0.5)")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--fit", choices=["pad", "crop"], default="pad",
                        help="pad = add black bars (safe), crop = fill frame cutting edges")
    args = parser.parse_args()

    require_ffmpeg()

    inputs = []
    for pattern in args.inputs:
        matches = sorted(Path().glob(pattern), key=natural_key) if any(c in pattern for c in "*?[]") else [Path(pattern)]
        inputs.extend(matches)
    inputs = [p for p in inputs if not p.name.startswith(".")]
    if not inputs:
        die("No input videos found.")
    for p in inputs:
        if not p.exists():
            die(f"Input not found: {p}")
    if len(inputs) == 1:
        print("Only one input given - result will be a normalized copy of it.")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Merging {len(inputs)} clip(s) into {out} "
          f"({args.width}x{args.height} @ {args.fps}fps, fit={args.fit})...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        parts = []
        for i, src in enumerate(inputs):
            print(f"  [{i + 1}/{len(inputs)}] Normalizing {src.name}...")
            part = tmp_dir / f"norm_{i:04d}.mp4"
            normalize(src, part, args.width, args.height, args.fps, args.fit)
            parts.append(part)

        merge_with_fades(parts, out, args.fade)

    final = probe_duration(out)
    print(f"Done: {out} ({final:.1f}s)")


if __name__ == "__main__":
    main()
