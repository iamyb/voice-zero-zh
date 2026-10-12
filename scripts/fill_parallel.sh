#!/usr/bin/env bash
# Fill all missing AISHELL-1 speakers in parallel.
# Usage: bash scripts/fill_parallel.sh [JOBS]
set -u
cd "$(dirname "$0")/.."
JOBS="${1:-8}"

# Collect missing speakers (in speaker.info but not yet in voices/aishell1/)
MISSING_FILE=$(mktemp)
awk '{print "S"$1}' metadata/aishell1/speaker.info | sort > /tmp/vzzh_all_speakers
ls voices/aishell1/*.wav 2>/dev/null | xargs -n1 basename | sed 's/\.wav//' | sort > /tmp/vzzh_have
comm -23 /tmp/vzzh_all_speakers /tmp/vzzh_have > "$MISSING_FILE"
echo "missing: $(wc -l < "$MISSING_FILE") speakers, jobs: $JOBS"

# Split into N chunks, run one build_voices.py per chunk in parallel
rm -f /tmp/vzzh_chunk_*
split -n "l/$JOBS" -d "$MISSING_FILE" /tmp/vzzh_chunk_
CHUNKS=(/tmp/vzzh_chunk_*)

pids=()
for i in "${!CHUNKS[@]}"; do
  speakers=$(tr '\n' ' ' < "${CHUNKS[$i]}")
  echo "[worker $i] $(echo $speakers | wc -w) speakers: $(echo $speakers | awk '{print $1"..."$NF}')"
  python3 scripts/build_voices.py --no-reindex $speakers > "/tmp/vzzh_worker_$i.log" 2>&1 &
  pids+=($!)
done

echo "waiting for ${#pids[@]} workers ..."
fail=0
for p in "${pids[@]}"; do
  wait "$p" || fail=$((fail+1))
done
echo "workers done, $fail failed"

# Final reindex
python3 scripts/reindex.py
rm -f /tmp/vzzh_chunk_* "$MISSING_FILE" /tmp/vzzh_all_speakers /tmp/vzzh_have
echo "aishell1 total: $(ls voices/aishell1/*.wav | wc -l) / 400"
