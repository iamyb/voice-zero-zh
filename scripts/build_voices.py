#!/usr/bin/env python3
"""Build reference audio from AISHELL-1 into the voice-zero-zh library.

For each requested speaker:
  1. Download the per-speaker tarball from HuggingFace (AISHELL/AISHELL-1,
     covers S0002-S0101); if not present there, fall back to the loose-file
     mirror (shenyunhang/AISHELL-1, covers all 119 speakers).
  2. Extract / collect the wavs into a temp dir.
  3. Pick the utterance whose duration is closest to the target (default 7s,
     must fall within MIN/MAX seconds).
  4. Clean it with ffmpeg: trim to target length, loudness-normalize to
     -8 LUFS (true peak -2 dB), resample to 16 kHz mono.
  5. Write voices/aishell1/<speaker>.wav and metadata/aishell1/<speaker>.json.

Finally (re)writes metadata/index.json for all voices across all sources.

Usage:
  python3 scripts/build_voices.py S0002 S0003 ...
  python3 scripts/build_voices.py --all-missing   # every speaker in speaker.info
  python3 scripts/build_voices.py --reindex       # only rebuild index.json

Requires: curl, tar, ffmpeg, ffprobe.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = "aishell1"
VOICES_DIR = os.path.join(REPO_ROOT, "voices", SOURCE)
METADATA_DIR = os.path.join(REPO_ROOT, "metadata", SOURCE)
SPEAKER_INFO = os.path.join(METADATA_DIR, "speaker.info")

# Primary source: per-speaker tarballs (covers S0002-S0101 only).
HF_BASE = "https://huggingface.co/datasets/AISHELL/AISHELL-1/resolve/main/data_aishell/wav"
# Fallback source: loose per-utterance files (covers all 119 speakers).
HF_LOOSE_BASE = "https://huggingface.co/datasets/shenyunhang/AISHELL-1"
DATASET = "AISHELL-1 (openslr.org/resources/33, HuggingFace: AISHELL/AISHELL-1)"
LICENSE = "Apache-2.0"

TARGET_SECONDS = 7.0
MIN_SECONDS = 5.0
MAX_SECONDS = 10.0


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def load_speaker_info():
    """Return {speaker_id: gender} from metadata/aishell1/speaker.info."""
    info = {}
    with open(SPEAKER_INFO, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                info["S" + parts[0]] = parts[1]
    return info


def download_tarball(speaker, workdir):
    """Download the per-speaker tarball. Returns None on 404."""
    tarball = os.path.join(workdir, f"{speaker}.tar.gz")
    url = f"{HF_BASE}/{speaker}.tar.gz"
    r = run(["curl", "-sL", "-o", tarball, url, "-w", "%{http_code}"])
    code = r.stdout.strip()
    if code == "404":
        return None
    if code != "200":
        raise RuntimeError(f"download failed for {speaker}: HTTP {code}")
    return tarball


def extract(tarball, workdir):
    dest = os.path.join(workdir, speaker_of(tarball))
    with tarfile.open(tarball) as tf:
        tf.extractall(dest)
    return dest


def speaker_of(tarball):
    return os.path.splitext(os.path.basename(tarball))[0]


def list_loose_files(speaker):
    """List utterance files for a speaker in the loose-file mirror."""
    url = (f"https://huggingface.co/api/datasets/shenyunhang/AISHELL-1/"
           f"tree/main/data_aishell/wav/train/{speaker}?limit=1000")
    r = run(["curl", "-sL", url])
    if r.returncode != 0:
        raise RuntimeError(f"file listing failed for {speaker}")
    entries = json.loads(r.stdout)
    return [e["path"] for e in entries if e["type"] == "file"]


LOOSE_MAX_PROBE = 60  # at most this many files to download before giving up


def download_loose(speaker, workdir):
    """Stream utterance wavs from the loose-file mirror, stopping early once a
    candidate close to TARGET_SECONDS is found. Returns (wav_dir, best_path)."""
    dest = os.path.join(workdir, speaker)
    os.makedirs(dest, exist_ok=True)
    paths = list_loose_files(speaker)
    if not paths:
        raise RuntimeError(f"no files found for {speaker} in loose mirror")
    best = None  # (abs_diff, path)
    for i, p in enumerate(paths[:LOOSE_MAX_PROBE]):
        out = os.path.join(dest, os.path.basename(p))
        url = f"{HF_LOOSE_BASE}/resolve/main/{p}"
        r = run(["curl", "-sL", "--fail", "-o", out, url])
        if r.returncode != 0:
            continue
        try:
            d = duration(out)
        except (ValueError, OSError):
            continue
        if MIN_SECONDS <= d <= MAX_SECONDS:
            diff = abs(d - TARGET_SECONDS)
            if best is None or diff < best[0]:
                best = (diff, out)
            if diff <= 0.3:
                break  # close enough
    if best is None:
        raise RuntimeError(
            f"no utterance in {MIN_SECONDS}-{MAX_SECONDS}s among first "
            f"{min(LOOSE_MAX_PROBE, len(paths))} files of {speaker}")
    return dest, best[1]


def fetch_wavs(speaker, workdir):
    """Get wavs for the speaker. Returns (wav_dir, source_file, preselected)."""
    tarball = download_tarball(speaker, workdir)
    if tarball is not None:
        return extract(tarball, workdir), f"data_aishell/wav/{speaker}.tar.gz", None
    print(f"      tarball not in primary mirror, using loose-file mirror ...")
    wav_dir, preselected = download_loose(speaker, workdir)
    return wav_dir, f"data_aishell/wav/train/{speaker}/", preselected


def pick_utterance(wav_dir):
    """Return the wav file whose duration is closest to TARGET_SECONDS."""
    candidates = []
    for root, _, files in os.walk(wav_dir):
        for name in files:
            if name.lower().endswith(".wav"):
                path = os.path.join(root, name)
                try:
                    d = duration(path)
                except (ValueError, OSError):
                    continue
                if MIN_SECONDS <= d <= MAX_SECONDS:
                    candidates.append((abs(d - TARGET_SECONDS), d, path))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def clean(src, dst):
    r = run(["ffmpeg", "-y", "-v", "error", "-i", src,
             "-t", str(TARGET_SECONDS),
             "-af", "loudnorm=I=-8:TP=-2:LRA=11,aresample=16000",
             "-ac", "1", dst])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {src}: {r.stderr.strip()}")


def build_one(speaker, info):
    out_wav = os.path.join(VOICES_DIR, f"{speaker}.wav")
    if os.path.exists(out_wav):
        print(f"[skip] {speaker} already exists")
        return False
    with tempfile.TemporaryDirectory(prefix=f"vzzh_{speaker}_") as workdir:
        print(f"[1/4] {speaker}: downloading ...")
        print(f"[2/4] {speaker}: extracting ...")
        wav_dir, source_file, preselected = fetch_wavs(speaker, workdir)
        print(f"[3/4] {speaker}: picking utterance ...")
        pick = preselected or pick_utterance(wav_dir)
        if pick is None:
            print(f"[fail] {speaker}: no utterance in {MIN_SECONDS}-{MAX_SECONDS}s range")
            return False
        src_rel = os.path.relpath(pick, wav_dir)
        print(f"[4/4] {speaker}: cleaning {src_rel} ({duration(pick):.1f}s) ...")
        clean(pick, out_wav)
    meta = {
        "id": speaker,
        "source": SOURCE,
        "gender": info.get(speaker, "unknown"),
        "language": "zh-CN",
        "duration_seconds": round(duration(out_wav), 2),
        "sample_rate": 16000,
        "origin": {
            "dataset": DATASET,
            "file": source_file,
            "utterance": src_rel,
        },
        "processing": (
            f"trimmed to {TARGET_SECONDS:.0f}s, loudnorm I=-8 LUFS TP=-2 dB, "
            "16 kHz mono (ffmpeg)"
        ),
        "license": LICENSE,
    }
    with open(os.path.join(METADATA_DIR, f"{speaker}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[done] {speaker} -> voices/{SOURCE}/{speaker}.wav ({meta['duration_seconds']}s)")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("speakers", nargs="*", help="speaker IDs, e.g. S0002")
    ap.add_argument("--all-missing", action="store_true",
                    help="build every speaker in speaker.info that is not yet in voices/")
    ap.add_argument("--reindex", action="store_true", help="only rebuild index.json")
    args = ap.parse_args()

    os.makedirs(VOICES_DIR, exist_ok=True)
    os.makedirs(METADATA_DIR, exist_ok=True)
    for tool in ("curl", "tar", "ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"required tool not found: {tool}")

    info = load_speaker_info()

    if args.all_missing:
        existing = {n[:-4] for n in os.listdir(VOICES_DIR) if n.endswith(".wav")}
        args.speakers = [s for s in info if s not in existing]

    if not args.speakers and not args.reindex:
        ap.print_help()
        return

    ok, failed = 0, []
    for speaker in args.speakers:
        try:
            if build_one(speaker, info):
                ok += 1
        except Exception as e:
            failed.append(speaker)
            print(f"[fail] {speaker}: {e}")

    # Rebuild the global index
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from reindex import reindex
    reindex()
    print(f"\n{ok} built, {len(failed)} failed {failed if failed else ''}")


if __name__ == "__main__":
    main()
