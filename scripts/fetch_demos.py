#!/usr/bin/env python3
"""Generic TTS-demo fetcher, driven by scripts/demo_sources.json.

For every source listed in the manifest, downloads each demo wav (paths are
URL-encoded so non-ASCII segments like 马云 work), cleans it with the same
pipeline (loudnorm -8 LUFS, 16 kHz mono), and writes:
  voices/<source>/<id>.wav
  metadata/<source>/<id>.json

Then rebuilds metadata/index.json.

Usage:
  python3 scripts/fetch_demos.py                 # all sources in the manifest
  python3 scripts/fetch_demos.py spark_tts_demo  # only the named source(s)

Requires: curl, ffmpeg, ffprobe.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import urllib.parse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_sources.json")
VOICES_ROOT = os.path.join(REPO_ROOT, "voices")
METADATA_ROOT = os.path.join(REPO_ROOT, "metadata")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def clean(src, dst):
    r = run(["ffmpeg", "-y", "-v", "error", "-i", src,
             "-af", "loudnorm=I=-8:TP=-2:LRA=11,aresample=16000",
             "-ac", "1", dst])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()}")


def fetch_one(source_cfg, vid, spec):
    source = source_cfg["source"]
    voices_dir = os.path.join(VOICES_ROOT, source)
    meta_dir = os.path.join(METADATA_ROOT, source)
    os.makedirs(voices_dir, exist_ok=True)
    os.makedirs(meta_dir, exist_ok=True)

    out_wav = os.path.join(voices_dir, f"{vid}.wav")
    if os.path.exists(out_wav):
        print(f"[skip] {source}/{vid} already exists")
        return False

    # URL-encode the path (handles non-ASCII segments), keep the slashes.
    rel = spec["path"]
    encoded = "/".join(urllib.parse.quote(seg) for seg in rel.split("/"))
    url = f"{source_cfg['base']}/{encoded}"

    tmp = os.path.join(voices_dir, f".tmp_{vid}.wav")
    r = run(["curl", "-sL", "--fail", "-o", tmp, url])
    if r.returncode != 0:
        print(f"[fail] {source}/{vid}: download failed ({url})")
        if os.path.exists(tmp):
            os.remove(tmp)
        return False

    try:
        clean(tmp, out_wav)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    meta = {
        "id": vid,
        "source": source,
        "gender": spec.get("gender", "unknown"),
        "language": spec.get("language", source_cfg.get("default_language", "zh-CN")),
        "duration_seconds": round(duration(out_wav), 2),
        "sample_rate": 16000,
        "origin": {
            "dataset": source_cfg["dataset"],
            "url": url,
            "fetched_at": datetime.date.today().isoformat(),
        },
        "processing": "loudnorm I=-8 LUFS TP=-2 dB, 16 kHz mono (ffmpeg)",
        "license": source_cfg["license"],
    }
    if "label" in spec:
        meta["label"] = spec["label"]
    if "note" in source_cfg:
        meta["note"] = source_cfg["note"]

    with open(os.path.join(meta_dir, f"{vid}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[done] {source}/{vid} ({meta['duration_seconds']}s)")
    return True


def main():
    for tool in ("curl", "ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"required tool not found: {tool}")

    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)

    only = set(sys.argv[1:])
    ok, failed = 0, []
    for source_cfg in manifest:
        if only and source_cfg["source"] not in only:
            continue
        print(f"=== {source_cfg['source']} ===")
        for vid, spec in source_cfg["files"].items():
            try:
                if fetch_one(source_cfg, vid, spec):
                    ok += 1
            except Exception as e:
                failed.append(f"{source_cfg['source']}/{vid}")
                print(f"[fail] {source_cfg['source']}/{vid}: {e}")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from reindex import reindex
    reindex()
    print(f"\n{ok} fetched, {len(failed)} failed {failed if failed else ''}")


if __name__ == "__main__":
    main()
