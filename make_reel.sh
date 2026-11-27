#!/usr/bin/env bash
# make_reel.sh - merge ALL videos from the input folder into one reel.
#
# Usage (from Git Bash, inside the repo folder):
#     bash make_reel.sh
#     bash make_reel.sh --fade 0.8
#     bash make_reel.sh --fade 0 --fit crop
#
# The input folder is the one configured in config.json (set from the web
# app), or the repo's input/ folder if no config exists. Results go to
# output/ with a timestamp in the name, so nothing gets overwritten.

set -e
cd "$(dirname "$0")"

input_dir="input"
if [ -f config.json ]; then
    configured=$(python -c "import json;print(json.load(open('config.json')).get('input_dir',''))" 2>/dev/null || true)
    if [ -n "$configured" ]; then
        input_dir="$configured"
    fi
fi

if [ ! -d "$input_dir" ]; then
    echo "Input folder not found: $input_dir"
    echo "Set the right folder in the web app, or edit config.json."
    exit 1
fi

shopt -s nullglob
clips=("$input_dir"/*.mp4 "$input_dir"/*.MP4 "$input_dir"/*.mov "$input_dir"/*.MOV \
       "$input_dir"/*.mkv "$input_dir"/*.webm "$input_dir"/*.avi)
shopt -u nullglob

if [ ${#clips[@]} -eq 0 ]; then
    echo "No videos found in $input_dir - put your clips there first."
    exit 1
fi

echo "Found ${#clips[@]} clip(s) in $input_dir, merging in alphabetical order:"
printf '  %s\n' "${clips[@]}"

mkdir -p output
out="output/reel_$(date +%Y%m%d_%H%M%S).mp4"

python merge_videos.py "${clips[@]}" -o "$out" "$@"

echo
echo "Reel ready: $out"
