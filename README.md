# AI Video Reels Agent

Automatic editing and publishing of short vertical videos (reels) about
meditation, therapy, philosophy, and personal growth.

What it does today:

- Removes long silences from a video, keeping a short natural pause
  (so meditation content still breathes)
- Merges multiple clips into one vertical reel (1080x1920) with
  crossfade transitions

What is coming next:

- Auto-captions with Whisper
- Publishing to YouTube Shorts via the YouTube Data API

## Project structure

```
AI_agent/
├── setup.ps1          <- run this ONCE to set everything up
├── install_git.ps1    <- optional: installs Git (only needed for git clone)
├── remove_silence.py  <- the silence remover script
├── merge_videos.py    <- the video merger script
├── make_reel.sh       <- one command: merges ALL clips from the input folder
├── app.py             <- simple web interface (run: python app.py)
├── start_app.bat      <- double-click launcher for the interface (Windows)
├── diagnose.py        <- tests everything, writes + uploads a diagnostic report
├── diagnostics/       <- diagnostic reports (uploaded to GitHub)
└── output/            <- finished reels appear here (created automatically)
```

Your clips can live anywhere: the web app lets you point the **input**
folder to any existing folder and the **output** folder to any location
(new output folders are created automatically). Both choices are saved
in `config.json`, which is not committed - they also apply to
`make_reel.sh`.

## Setup (Windows, one time)

1. Install Python from https://www.python.org/downloads/
   (tick **Add Python to PATH** during installation).
2. Save/download this project to a folder, e.g. `C:\reels`.
3. In PowerShell, inside that folder, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```

This installs FFmpeg (via winget).

## Usage

Point the app to your clips folder (in the web page, or edit
`config.json`), put a video there, then:

```powershell
python remove_silence.py "C:\path\to\myvideo.mp4"
```

Result: `myvideo_tight.mp4` next to the original, with every long gap
shortened to a small pause. The script prints every silence it found and
how much time was saved.

### Tuning

| Option           | Default | Meaning                                              |
| ---------------- | ------- | ---------------------------------------------------- |
| `--min-silence`  | `1.0`   | Only gaps longer than this (seconds) are shortened   |
| `--keep`         | `0.3`   | Seconds of pause kept inside each gap                |
| `--noise`        | `-35`   | Volume (dB) below which audio counts as silence      |
| `-o PATH`        | —       | Custom output path                                   |

For calm meditation content, try `--min-silence 1.5 --keep 0.5` so the
pacing stays relaxed. For talking-head clips, try `--min-silence 0.6`.

## Merging multiple clips into one reel

```powershell
python merge_videos.py part1.mp4 part2.mp4 part3.mp4
```

Result: `output\reel.mp4` in vertical 1080x1920 (9:16, perfect for
YouTube Shorts), with a 0.5s crossfade between clips.

You can also use a wildcard to take clips in name order:

```powershell
python merge_videos.py "C:\path\to\clips\part*.mp4"
```

### Tuning

| Option      | Default | Meaning                                                       |
| ----------- | ------- | ------------------------------------------------------------- |
| `--fade`    | `0.5`   | Crossfade seconds between clips (`0` = hard cut)              |
| `--fit`     | `pad`   | `pad` = black bars around odd shapes, `crop` = fill and cut   |
| `--fps`     | `30`    | Output frame rate                                             |
| `--width` / `--height` | `1080` / `1920` | Output resolution                      |
| `-o PATH`   | —       | Custom output path                                            |

Use `--fit crop` when you want clips to fill the whole vertical frame
(edges get cut) instead of showing black bars.

## The easy way: one command

From Git Bash, inside the repo folder:

```bash
bash make_reel.sh
```

That merges **every video in your input folder** (the one set in the web
app or `config.json`; default `input/`, in alphabetical order) into one
reel saved as `output/reel_YYYYMMDD_HHMMSS.mp4` - each run gets its own
timestamped file, so nothing is ever overwritten. Extra options are
passed through:

```bash
bash make_reel.sh --fade 0.8
bash make_reel.sh --fade 0 --fit crop
```

## The simple interface

```powershell
python app.py
```

(or double-click `start_app.bat`). A page opens at
http://localhost:8765 where you can:

- remove silence from any video in your input folder with one click
- merge all clips in your input folder into one reel
- run diagnostics
- watch the live log and see the results in the output folder
- change the input and output folders (saved in `config.json`)

The server runs only on your own computer (localhost) - nothing is
exposed to the network.

## Diagnostics

If something does not work, run:

```powershell
python diagnose.py
```

It checks Python, FFmpeg, and the project files, then runs a real
functional test of both scripts on tiny synthetic videos. The report is
saved in `diagnostics/` and (if all tests pass) automatically committed
and pushed to GitHub, so it can be shared when asking for help. Use
`python diagnose.py --no-push` to keep the report local.

## Roadmap

1. **Phase 1 - Editing core**: silence removal (done), merging clips (done)
2. **Phase 2 - AI polish**: Whisper auto-captions, auto titles/descriptions
3. **Phase 3 - Publishing**: YouTube Shorts upload via YouTube Data API
4. **Phase 4 - Orchestration**: one command per reel, then watch-folder automation
