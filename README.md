# AI Video Reels Agent

Automatic editing and publishing of short vertical videos (reels) about
meditation, therapy, philosophy, and personal growth.

What it does today:

- Removes long silences from a video, keeping a short natural pause
  (so meditation content still breathes)

What is coming next:

- Merge multiple clips into one reel with smooth transitions
- Auto-captions with Whisper
- Publishing to YouTube Shorts via the YouTube Data API

## Project structure

```
AI_agent/
├── setup.ps1          <- run this ONCE to set everything up
├── remove_silence.py  <- the silence remover script
├── input/             <- put your raw videos here
├── output/            <- finished videos appear here
└── temp/              <- scratch space (can be deleted any time)
```

## Setup (Windows, one time)

1. Install Python from https://www.python.org/downloads/
   (tick **Add Python to PATH** during installation).
2. Save/download this project to a folder, e.g. `C:\reels`.
3. In PowerShell, inside that folder, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```

This installs FFmpeg (via winget) and creates the `input`, `output`,
and `temp` folders.

## Usage

Put a video in the `input\` folder, then:

```powershell
python remove_silence.py input\myvideo.mp4
```

Result: `input\myvideo_tight.mp4`, with every long gap shortened to a
small pause. The script prints every silence it found and how much time
was saved.

### Tuning

| Option           | Default | Meaning                                              |
| ---------------- | ------- | ---------------------------------------------------- |
| `--min-silence`  | `1.0`   | Only gaps longer than this (seconds) are shortened   |
| `--keep`         | `0.3`   | Seconds of pause kept inside each gap                |
| `--noise`        | `-35`   | Volume (dB) below which audio counts as silence      |
| `-o PATH`        | —       | Custom output path                                   |

For calm meditation content, try `--min-silence 1.5 --keep 0.5` so the
pacing stays relaxed. For talking-head clips, try `--min-silence 0.6`.

## Roadmap

1. **Phase 1 - Editing core**: silence removal (done), merging clips
2. **Phase 2 - AI polish**: Whisper auto-captions, auto titles/descriptions
3. **Phase 3 - Publishing**: YouTube Shorts upload via YouTube Data API
4. **Phase 4 - Orchestration**: one command per reel, then watch-folder automation
