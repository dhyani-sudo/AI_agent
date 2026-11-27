#!/usr/bin/env bash
# make_reel.sh - merge ALL videos in input/ into one reel, ready for YouTube Shorts.
#
# Usage (from Git Bash, inside the repo folder):
#     bash make_reel.sh
#     bash make_reel.sh --fade 0.8
#     bash make_reel.sh --fade 0 --fit crop
#
# The result appears in output/ with a timestamp in its name, so every
# run keeps its own reel and nothing gets overwritten.

set -e
cd "$(dirname "$0")"

shopt -s nullglob
clips=(input/*.mp4 input/*.MP4 input/*.mov input/*.MOV input/*.mkv input/*.webm input/*.avi)
shopt -u nullglob

if [ ${#clips[@]} -eq 0 ]; then
    echo "No videos found in input/ - put your clips there first."
    exit 1
fi

echo "Found ${#clips[@]} clip(s), merging in alphabetical order:"
printf '  %s\n' "${clips[@]}"

mkdir -p output
out="output/reel_$(date +%Y%m%d_%H%M%S).mp4"

python merge_videos.py "${clips[@]}" -o "$out" "$@"

echo
echo "Reel ready: $out"
