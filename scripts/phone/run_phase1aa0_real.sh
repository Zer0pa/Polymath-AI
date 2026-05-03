#!/system/bin/sh
# Phase 1A.A.0 phone-side runner — runs qwen_frozen_subgraph against a
# multi-input list (real-tokenized hidden states) for cosine-similarity
# validation against the host CPU reference.
#
# Usage from adb shell:
#   sh /sdcard/Polymath/phase1a/run_phase1aa0_real.sh
#
# Pre-conditions:
#   /data/local/tmp/phase1a/qwen_frozen_subgraph.qnn.bin   (already there from Phase 1A)
#   /data/local/tmp/phase1a/inputs_real/input_NNN.bin      (pushed via ADB)
#   /data/local/tmp/phase1a/inputs_real/input_list.txt     (pushed via ADB; 20 lines)
#   /data/local/tmp/qairt-2.44/                            (already there)
#
# Output:
#   /data/local/tmp/phase1a/output_phase1aa0_real/Result_<i>/serving_default_output_0_output.raw
set -e
QAIRT=/data/local/tmp/qairt-2.44
ROOT=/data/local/tmp/phase1a
INPUTS=$ROOT/inputs_real
OUT=$ROOT/output_phase1aa0_real

export LD_LIBRARY_PATH=$QAIRT/lib/aarch64-android:$LD_LIBRARY_PATH
export ADSP_LIBRARY_PATH="$QAIRT/lib/hexagon-v79/unsigned;$QAIRT/lib/hexagon-v75/unsigned;$QAIRT/lib/hexagon-v81/unsigned;/dsp"

cd "$INPUTS" || exit 99
rm -rf "$OUT"
mkdir -p "$OUT"

echo "=== Phase 1A.A.0 real-data inference on Hexagon NPU ==="
echo "Backend: $QAIRT/lib/aarch64-android/libQnnHtp.so"
echo "Binary:  $ROOT/qwen_frozen_subgraph.qnn.bin (2.3 GB Qwen2.5-1.5B layers 1..26)"
echo "Inputs:  $INPUTS  ($(wc -l < input_list.txt) sequences)"
echo "Output:  $OUT"
echo

T0=$(date +%s%3N 2>/dev/null || date +%s)
$QAIRT/bin/aarch64-android/qnn-net-run \
  --retrieve_context "$ROOT/qwen_frozen_subgraph.qnn.bin" \
  --backend $QAIRT/lib/aarch64-android/libQnnHtp.so \
  --input_list input_list.txt \
  --output_dir "$OUT" 2>&1 | tail -10
T1=$(date +%s%3N 2>/dev/null || date +%s)

N=$(wc -l < input_list.txt | tr -d ' ')
DT_MS=$((T1 - T0))
PER=$(( DT_MS / N ))
echo
echo "===timing==="
echo "Total: ${DT_MS} ms; per inference: ${PER} ms (n=${N})"
echo
echo "===output-listing==="
ls -la "$OUT/" | head -25
echo
echo "===saturation-stats==="
df -h /data/local/tmp 2>/dev/null | tail -1
echo "Battery: $(dumpsys battery | grep -E 'level|temperature|powered' | head -3)"
