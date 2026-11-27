#!/usr/bin/env python3
"""Remove long silences from a video while keeping a short natural pause.

Usage:
    python remove_silence.py input/myvideo.mp4
    python remove_silence.py input/myvideo.mp4 -o output/myvideo_tight.mp4
    python remove_silence.py input/myvideo.mp4 --min-silence 1.0 --keep 0.4 --noise -40
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def require_ffmpeg() -> None:
    if not shutil_which("ffmpeg"):
        die(
            "FFmpeg not found. Run setup.ps1 first, or install FFmpeg and "
            "make sure 'ffmpeg -version' works in PowerShell."
        )


def shutil_which(name: str):
    from shutil import which
    return which(name)


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
        die("Could not read video duration. Is this a valid video file?")


def detect_silences(path: Path, noise_db: float, min_silence: float):
    print(f"Scanning for silences (longer than {min_silence}s, below {noise_db} dB)...")
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats",
            "-i", str(path),
            "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    log = result.stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
    silences = list(zip(starts, ends))
    if len(starts) > len(ends):
        # silence running until the very end of the file
        silences.append((starts[-1], None))
    return silences


def build_keep_ranges(duration: float, silences, keep: float):
    ranges = []
    cursor = 0.0
    for start, end in silences:
        end = duration if end is None else end
        cut_start = start + keep / 2
        cut_end = end - keep / 2
        if cut_end <= cut_start:
            continue
        if cut_start > cursor:
            ranges.append((cursor, cut_start))
        cursor = max(cursor, cut_end)
    if cursor < duration:
        ranges.append((cursor, duration))
    return ranges


def extract_range(src: Path, start: float, end: float, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove long silences from a video, keeping a short pause."
    )
    parser.add_argument("input", help="Path to the input video")
    parser.add_argument("-o", "--output", help="Output path (default: <input>_tight.mp4)")
    parser.add_argument("--min-silence", type=float, default=1.0,
                        help="Only gaps longer than this many seconds are shortened (default: 1.0)")
    parser.add_argument("--keep", type=float, default=0.3,
                        help="Seconds of pause to keep inside each gap (default: 0.3)")
    parser.add_argument("--noise", type=float, default=-35.0,
                        help="Volume in dB below which audio counts as silence (default: -35)")
    args = parser.parse_args()

    require_ffmpeg()

    src = Path(args.input)
    if not src.exists():
        die(f"Input file not found: {src}")

    out = Path(args.output) if args.output else src.with_name(src.stem + "_tight.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(src)
    silences = detect_silences(src, args.noise, args.min_silence)

    if not silences:
        print("No silences found - nothing to trim. The video stays as it is.")
        return

    print(f"Found {len(silences)} silence(s):")
    for start, end in silences:
        end_str = f"{end:.1f}s" if end is not None else "end of video"
        print(f"  - {start:.1f}s -> {end_str}")

    ranges = build_keep_ranges(duration, silences, args.keep)
    kept = sum(e - s for s, e in ranges)
    saved = duration - kept

    print(f"Tightening video: {len(ranges)} segment(s), saving {saved:.1f}s "
          f"({(saved / duration) * 100:.0f}% shorter)...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        part_files = []
        for i, (start, end) in enumerate(ranges):
            part = tmp_dir / f"part_{i:04d}.mp4"
            extract_range(src, start, end, part)
            part_files.append(part)

        list_file = tmp_dir / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in part_files), encoding="utf-8"
        )
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-c", "copy", "-movflags", "+faststart", str(out),
            ],
            check=True,
        )

    print(f"Done: {out}")
    print(f"Original: {duration:.1f}s  ->  New: {kept:.1f}s  (saved {saved:.1f}s)")


if __name__ == "__main__":
    main()
