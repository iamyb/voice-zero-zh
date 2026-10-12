#!/usr/bin/env python3
"""Fetch official IndexTTS demo audio as reference voices.

Downloads demo wavs from the IndexTTS GitHub repo (assets/), cleans them
with the same pipeline (loudnorm -8 LUFS, 16 kHz mono), and writes to
voices/indextts_demo/ + metadata/indextts_demo/.

Usage:
  python3 scripts/fetch_indextts_demo.py
"""

import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = "indextts_demo"
VOICES_DIR = os.path.join(REPO_ROOT, "voices", SOURCE)
METADATA_DIR = os.path.join(REPO_ROOT, "metadata", SOURCE)

# Demo files from the IndexTTS repo (raw GitHub URLs)
BASE = "https://raw.githubusercontent.com/index-tts/index-tts/main/examples"
DEMOS = [
    ("voice_01", "voice_01.wav"),
    ("voice_02", "voice_02.wav"),
    ("voice_03", "voice_03.wav"),
    ("voice_04", "voice_04.wav"),
    ("voice_05", "voice_05.wav"),
    ("voice_06", "voice_06.wav"),
    ("voice_07", "voice_07.wav"),
    ("voice_08", "voice_08.wav"),
    ("voice_09", "voice_09.wav"),
    ("voice_11", "voice_11.wav"),
    ("voice_12", "voice_12.wav"),
    ("emo_sad", "emo_sad.wav"),
    ("emo_hate", "emo_hate.wav"),
]

LICENSE = "See IndexTTS repo LICENSE"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def fetch_one(vid, filename):
    out_wav = os.path.join(VOICES_DIR, f"{vid}.wav")
    if os.path.exists(out_wav):
        print(f"[skip] {vid} already exists")
        return False

    url = f"{BASE}/{filename}"
    tmp = os.path.join(VOICES_DIR, f".tmp_{vid}.wav")
    r = run(["curl", "-sL", "--fail", "-o", tmp, url])
    if r.returncode != 0:
        print(f"[fail] {vid}: download failed ({url})")
        if os.path.exists(tmp):
            os.remove(tmp)
        return False

    # Clean: loudnorm + 16kHz mono
    r = run(["ffmpeg", "-y", "-v", "error", "-i", tmp,
             "-af", "loudnorm=I=-8:TP=-2:LRA=11,aresample=16000",
             "-ac", "1", out_wav])
    os.remove(tmp)
    if r.returncode != 0:
        print(f"[fail] {vid}: ffmpeg failed: {r.stderr.strip()}")
        return False

    meta = {
        "id": vid,
        "source": SOURCE,
        "gender": "unknown",
        "language": "zh-CN",
        "duration_seconds": round(duration(out_wav), 2),
        "sample_rate": 16000,
        "origin": {
            "dataset": "IndexTTS official demo",
            "url": url,
            "fetched_at": "2026-10-12",
        },
        "processing": "loudnorm I=-8 LUFS TP=-2 dB, 16 kHz mono (ffmpeg)",
        "license": LICENSE,
    }
    with open(os.path.join(METADATA_DIR, f"{vid}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[done] {vid} -> voices/{SOURCE}/{vid}.wav ({meta['duration_seconds']}s)")
    return True


def main():
    os.makedirs(VOICES_DIR, exist_ok=True)
    os.makedirs(METADATA_DIR, exist_ok=True)
    for tool in ("curl", "ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"required tool not found: {tool}")

    ok, failed = 0, []
    for vid, fname in DEMOS:
        try:
            if fetch_one(vid, fname):
                ok += 1
        except Exception as e:
            failed.append(vid)
            print(f"[fail] {vid}: {e}")

    # Rebuild global index
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from reindex import reindex
    reindex()
    print(f"\n{ok} fetched, {len(failed)} failed {failed if failed else ''}")


if __name__ == "__main__":
    main()
