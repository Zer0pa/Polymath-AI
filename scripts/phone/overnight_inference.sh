#!/system/bin/sh
# Phase 1A overnight inference chain — runs inside adb shell context.
#
# Loops qwen_frozen_subgraph + qwen_block on Hexagon NPU until either:
#   (a) the operator touches /sdcard/Polymath/phase1a/STOP
#   (b) battery temperature > 45.0 C  (thermal safety)
#   (c) battery level < 15%           (low-battery safety)
#   (d) /data/local/tmp/phase1a/qwen_frozen_subgraph.qnn.bin disappears
#
# Each iteration:
#   - Picks scope by round-robin (block, frozen) — block is fast, frozen is slow
#   - Runs qnn-net-run, captures wall-clock + exit code
#   - Reads battery + thermal_zones + meminfo
#   - Appends one JSON line to /sdcard/Polymath/phase1a/audit.jsonl
#
# The audit log is on /sdcard so it survives ADB disconnect, accessible by
# Termux for HF heartbeat push, and `adb pull`-able anytime.
#
# Prerequisites already on phone:
#   /data/local/tmp/qairt-2.44/...
#   /data/local/tmp/phase1a/qwen_block.qnn.bin
#   /data/local/tmp/phase1a/qwen_frozen_subgraph.qnn.bin
#   /data/local/tmp/phase1a/input.bin
#   /data/local/tmp/phase1a/input_list.txt
#
# Start with:
#   adb shell 'nohup setsid sh /sdcard/Polymath/phase1a/overnight_inference.sh \
#     > /sdcard/Polymath/phase1a/runner.log 2>&1 &'
#
# Stop with:
#   adb shell 'touch /sdcard/Polymath/phase1a/STOP'

set +e
QAIRT=/data/local/tmp/qairt-2.44
ROOT=/data/local/tmp/phase1a
LOGDIR=/sdcard/Polymath/phase1a
mkdir -p "$LOGDIR"
AUDIT="$LOGDIR/audit.jsonl"
STOP="$LOGDIR/STOP"
STATUS="$LOGDIR/status.json"
HF_TOKEN_FILE=/sdcard/Polymath/.hf-token
HF_REPO="Architect-Prime/polymath-telemetry"
HF_PUSH_EVERY=10  # push to HF every N iterations

# Safety thresholds
BATT_TEMP_MAX_DC=450   # 45.0 C in dC (deci-Celsius); battery temperature is reported in dC
BATT_LEVEL_MIN=15

export LD_LIBRARY_PATH=$QAIRT/lib/aarch64-android:$LD_LIBRARY_PATH
export ADSP_LIBRARY_PATH="$QAIRT/lib/hexagon-v79/unsigned;$QAIRT/lib/hexagon-v75/unsigned;$QAIRT/lib/hexagon-v81/unsigned;/dsp"

# Important: qnn-net-run resolves input_list paths relative to cwd. We must
# run from $ROOT so 'input.bin' (relative path in input_list.txt) resolves.
cd "$ROOT" || exit 99

run_id="$(date -u +%Y%m%dT%H%M%SZ)_phase1a_overnight"
echo "[overnight] run_id=$run_id"
echo "[overnight] audit=$AUDIT"

# HF push helper. Reads $AUDIT, base64-encodes it, POSTs as a single-file
# commit to https://huggingface.co/datasets/$HF_REPO/blob/main/phase1a/<run_id>/audit.jsonl
# Operator can monitor live by visiting that URL in any browser.
hf_push() {
  if [ ! -f "$HF_TOKEN_FILE" ] || [ ! -s "$AUDIT" ]; then
    echo "[hf_push] skip: token=$HF_TOKEN_FILE audit_size=$(wc -c < "$AUDIT" 2>/dev/null)" >> "$LOGDIR/hf_push.log"
    return 0
  fi
  HF_TOKEN=$(cat "$HF_TOKEN_FILE" | tr -d '\n\r ')
  B64=$(base64 -w 0 "$AUDIT" 2>/dev/null || base64 "$AUDIT" | tr -d '\n\r ')
  TMPND="$LOGDIR/.hf_ndjson"
  printf '{"key":"header","value":{"summary":"phase1a heartbeat %s","description":""}}\n{"key":"file","value":{"path":"phase1a/%s/audit.jsonl","content":"%s","encoding":"base64"}}\n' \
    "$run_id" "$run_id" "$B64" > "$TMPND"
  http_code=$(curl -sS -m 60 -X POST \
    -H "Authorization: Bearer $HF_TOKEN" \
    -H "Content-Type: application/x-ndjson" \
    --data-binary "@$TMPND" \
    -w '%{http_code}' \
    -o "$LOGDIR/hf_push_resp.json" \
    "https://huggingface.co/api/datasets/$HF_REPO/commit/main" 2>>"$LOGDIR/hf_push.log")
  echo "[hf_push] iter=$iter http=$http_code resp_head=$(head -c 200 "$LOGDIR/hf_push_resp.json" 2>/dev/null)" >> "$LOGDIR/hf_push.log"
  rm -f "$TMPND"
}

# Initial event
prev_event_hash=""
record_event() {
  # $1 = event type, $2 = scope or empty, $3 = payload-json (one-line)
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  scope="$2"
  payload="$3"

  # Read battery state
  bat_text=$(dumpsys battery 2>/dev/null)
  bat_level=$(echo "$bat_text" | grep " level:" | head -1 | awk '{print $2}')
  bat_temp=$(echo "$bat_text" | grep "temperature:" | head -1 | awk '{print $2}')
  bat_status=$(echo "$bat_text" | grep " status:" | head -1 | awk '{print $2}')
  bat_ac=$(echo "$bat_text" | grep "AC powered:" | head -1 | awk '{print $3}')

  # Thermal zones (CPU + Hexagon if present)
  thermal=""
  for f in /sys/class/thermal/thermal_zone[0-9]*; do
    [ -r "$f/type" ] && [ -r "$f/temp" ] || continue
    tname=$(cat "$f/type" 2>/dev/null)
    tval=$(cat "$f/temp" 2>/dev/null)
    case "$tname" in
      *cpu*|*skin*|*battery*|*aoss*|*npu*|*hexagon*)
        thermal="$thermal\"$tname\":$tval,"
        ;;
    esac
  done
  thermal="{${thermal%,}}"

  # Memory state (just total + available)
  mem_avail=$(grep "^MemAvailable:" /proc/meminfo 2>/dev/null | awk '{print $2}')
  mem_total=$(grep "^MemTotal:" /proc/meminfo 2>/dev/null | awk '{print $2}')

  # Disk free for /data and /sdcard
  disk_data=$(df /data | tail -1 | awk '{print $4}')
  disk_sdcard=$(df /sdcard | tail -1 | awk '{print $4}')

  # Build the row
  row="{\"ts\":\"$ts\",\"run_id\":\"$run_id\",\"event_type\":\"$1\",\"scope\":\"$scope\",\"payload\":$payload,\"battery\":{\"level\":$bat_level,\"temp_dC\":$bat_temp,\"status\":$bat_status,\"ac_powered\":\"$bat_ac\"},\"thermal\":$thermal,\"memory\":{\"avail_kb\":$mem_avail,\"total_kb\":$mem_total},\"disk\":{\"data_free_kb\":$disk_data,\"sdcard_free_kb\":$disk_sdcard},\"prev_event_hash\":\"$prev_event_hash\"}"

  # Append to audit log (atomic append, one line)
  echo "$row" >> "$AUDIT"

  # Compute hash for chain (sha256 of this line; used by next event)
  prev_event_hash=$(echo -n "$row" | sha256sum | awk '{print $1}')

  # Status snapshot (just the latest line, for quick remote inspection)
  echo "$row" > "$STATUS"
}

iter=0
record_event "phase1a_overnight_start" "" "{\"qnn_binaries_present\":[\"qwen_block\",\"qwen_frozen_subgraph\"]}"

while true; do
  iter=$((iter + 1))

  # Kill-switch
  if [ -f "$STOP" ]; then
    record_event "stop_signal_received" "" "{\"reason\":\"operator_touch_STOP\",\"iter\":$iter}"
    break
  fi

  # Sanity: required artifacts still present
  if [ ! -f "$ROOT/qwen_frozen_subgraph.qnn.bin" ] || [ ! -f "$ROOT/qwen_block.qnn.bin" ] || [ ! -f "$ROOT/input.bin" ]; then
    record_event "fatal_missing_artifact" "" "{\"reason\":\"required_qnn_bin_missing\",\"iter\":$iter}"
    break
  fi

  # Battery thermal safety
  bat_temp_dC=$(dumpsys battery 2>/dev/null | grep "temperature:" | head -1 | awk '{print $2}')
  if [ -n "$bat_temp_dC" ] && [ "$bat_temp_dC" -gt "$BATT_TEMP_MAX_DC" ] 2>/dev/null; then
    record_event "thermal_halt" "" "{\"battery_temp_dC\":$bat_temp_dC,\"threshold_dC\":$BATT_TEMP_MAX_DC,\"iter\":$iter}"
    break
  fi

  # Battery level safety
  bat_level=$(dumpsys battery 2>/dev/null | grep " level:" | head -1 | awk '{print $2}')
  if [ -n "$bat_level" ] && [ "$bat_level" -lt "$BATT_LEVEL_MIN" ] 2>/dev/null; then
    record_event "low_battery_halt" "" "{\"battery_level\":$bat_level,\"threshold\":$BATT_LEVEL_MIN,\"iter\":$iter}"
    break
  fi

  # Pick scope by round-robin: 9x qwen_block (fast, ~50ms each), 1x qwen_frozen_subgraph (slow, ~1s)
  if [ $((iter % 10)) -eq 0 ]; then
    scope=qwen_frozen_subgraph
    n=10
  else
    scope=qwen_block
    n=100
  fi
  out_dir="$ROOT/output_overnight_${scope}"
  mkdir -p "$out_dir"

  # Run inference
  t0=$(date +%s%3N 2>/dev/null || date +%s)
  $QAIRT/bin/aarch64-android/qnn-net-run \
    --retrieve_context "$ROOT/${scope}.qnn.bin" \
    --backend $QAIRT/lib/aarch64-android/libQnnHtp.so \
    --input_list "$ROOT/input_list.txt" \
    --output_dir "$out_dir" \
    --num_inferences $n \
    > /tmp/.qnn_$$.log 2>&1
  rc=$?
  t1=$(date +%s%3N 2>/dev/null || date +%s)
  dt_ms=$((t1 - t0))

  out_size=0
  if [ -f "$out_dir/Result_0/serving_default_output_0_output.raw" ]; then
    out_size=$(stat -c %s "$out_dir/Result_0/serving_default_output_0_output.raw" 2>/dev/null || echo 0)
  fi

  # Sample a few output bytes for sanity (32 bytes -> 8 floats hex).
  # tr -d '\n\r ' is critical — Android xxd wraps long lines at column 60, which
  # would otherwise inject a newline into the JSON value and split the audit
  # row across two lines on disk. We force one continuous hex string.
  head_bytes=""
  if [ "$out_size" -gt 0 ]; then
    head_bytes=$(head -c 32 "$out_dir/Result_0/serving_default_output_0_output.raw" 2>/dev/null | xxd -p 2>/dev/null | tr -d '\n\r ' | head -c 64)
  fi

  payload="{\"iter\":$iter,\"scope\":\"$scope\",\"num_inferences\":$n,\"wall_ms\":$dt_ms,\"per_inf_ms\":$((dt_ms / n)),\"rc\":$rc,\"out_size\":$out_size,\"out_head_hex\":\"$head_bytes\"}"
  record_event "inference_batch" "$scope" "$payload"
  rm -f /tmp/.qnn_$$.log

  # HF push every N iterations
  if [ $((iter % HF_PUSH_EVERY)) -eq 0 ]; then
    hf_push
  fi

  # Brief sleep between batches to avoid thermal runaway (10 s; tunable)
  sleep 10
done

record_event "phase1a_overnight_end" "" "{\"final_iter\":$iter}"
echo "[overnight] done at iter=$iter"
