#!/system/bin/sh
# Phase 1A on-device QNN inference runner.
#
# Run this INSIDE adb shell (or after sshing into Termux). It loads a
# pre-extracted QNN context binary (from scripts/host/extract_qnn_context.py)
# and runs ``qnn-net-run`` against ``libQnnHtp.so`` on Hexagon NPU.
#
# Usage:
#   adb push <scope>.qnn.bin /data/local/tmp/phase1a/
#   adb push input.bin /data/local/tmp/phase1a/  # raw FP32 input matching scope's input shape
#   echo "input.bin" > /data/local/tmp/phase1a/input_list.txt
#   adb shell sh /data/local/tmp/phase1a/run_qnn_inference.sh <scope> [num_inferences]
#
# Prerequisites already on phone:
#   /data/local/tmp/qairt-2.44/        - QAIRT 2.44.0.260225 aarch64-android
#                                        + Hexagon v75/v79/v81 unsigned skel
#   /data/local/tmp/phase1a/<scope>.qnn.bin
#   /data/local/tmp/phase1a/input.bin
#   /data/local/tmp/phase1a/input_list.txt   (one path per line)
#
# Args:
#   $1 = scope name (e.g. qwen_block, qwen_frozen_subgraph)
#   $2 = num inferences (default 10)
set -e
SCOPE=${1:-qwen_block}
N=${2:-10}
QAIRT=/data/local/tmp/qairt-2.44
ROOT=/data/local/tmp/phase1a

export LD_LIBRARY_PATH=$QAIRT/lib/aarch64-android:$LD_LIBRARY_PATH
export ADSP_LIBRARY_PATH="$QAIRT/lib/hexagon-v79/unsigned;$QAIRT/lib/hexagon-v75/unsigned;$QAIRT/lib/hexagon-v81/unsigned;/dsp"

cd $ROOT
mkdir -p output_${SCOPE}

echo "=== Phase 1A QNN inference: scope=$SCOPE n=$N ==="
echo "QAIRT: v2.44.0.260225 aarch64-android"
echo "Backend: $QAIRT/lib/aarch64-android/libQnnHtp.so"
echo "Hexagon skel search: $ADSP_LIBRARY_PATH"

/system/bin/time \
  $QAIRT/bin/aarch64-android/qnn-net-run \
    --retrieve_context ${SCOPE}.qnn.bin \
    --backend $QAIRT/lib/aarch64-android/libQnnHtp.so \
    --input_list input_list.txt \
    --output_dir output_${SCOPE} \
    --num_inferences $N

echo
echo "=== outputs ==="
ls -la output_${SCOPE}/Result_0/
