#!/usr/bin/env python3
"""Rebuild metadata/index.json by scanning all voices/<source>/*.wav.

Usage:
  python3 scripts/reindex.py
"""

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICES_ROOT = os.path.join(REPO_ROOT, "voices")
METADATA_ROOT = os.path.join(REPO_ROOT, "metadata")
INDEX_PATH = os.path.join(METADATA_ROOT, "index.json")


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def reindex():
    entries = []
    if not os.path.isdir(VOICES_ROOT):
        print("voices/ directory not found, nothing to index")
        return

    for source in sorted(os.listdir(VOICES_ROOT)):
        src_dir = os.path.join(VOICES_ROOT, source)
        if not os.path.isdir(src_dir):
            continue
        for name in sorted(os.listdir(src_dir)):
            if not name.endswith(".wav"):
                continue
            vid = name[:-4]
            wav_path = os.path.join(src_dir, name)
            meta_path = os.path.join(METADATA_ROOT, source, f"{vid}.json")

            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            else:
                meta = {"id": vid, "source": source}

            # Ensure required fields
            meta.setdefault("id", vid)
            meta.setdefault("source", source)
            meta["file"] = f"voices/{source}/{name}"
            if "duration_seconds" not in meta:
                try:
                    meta["duration_seconds"] = round(duration(wav_path), 2)
                except (ValueError, OSError):
                    meta["duration_seconds"] = None
            entries.append(meta)

    index = {
        "count": len(entries),
        "sources": sorted({e["source"] for e in entries}),
        "voices": entries,
    }
    os.makedirs(METADATA_ROOT, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"index.json written: {len(entries)} voices from {len(index['sources'])} source(s)")


if __name__ == "__main__":
    reindex()
