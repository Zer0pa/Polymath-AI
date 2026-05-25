#!/system/bin/sh
set -u
ROOT=/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h
RUN_ID=20260524T210920Z_phase13_gemma4_only_heterogeneous_p13h_20260524T232423Z
RUNNER=/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/bin/phase11_runner
LAYER_RUNNER=/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/bin/gemma4_layer_runner
SAFETY_LOG=/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_20260524T210920Z_phase13_gemma4_only_heterogeneous_p13h_20260524T232423Z_safety.jsonl
LOG="$ROOT/p13h_${RUN_ID}_chain.log"
EVENTS="$ROOT/p13h_${RUN_ID}_chain_events.jsonl"
STATE="$ROOT/p13h_${RUN_ID}_chain_state.json"
STOP="$ROOT/STOP_p13h_chain_${RUN_ID}"
BOOTSTRAP="$ROOT/p13h_${RUN_ID}_chain.bootstrap.log"
write_state() { printf '{"schema_version":"phase13_p13h_detached_chain_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\n' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }
thermal_monitor() { while true; do TS="$(date +%s)"; BAT="$(dumpsys battery 2>/dev/null | awk '/temperature:/ {print $2; exit}')"; MAX=0; MAXTYPE=unknown; for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/temp" ] || continue; T="$(cat "$z/temp" 2>/dev/null)"; Y="$(cat "$z/type" 2>/dev/null)"; case "$T" in -*) continue;; ""|*[!0-9]*) continue;; esac; if [ "$T" -gt "$MAX" ]; then MAX="$T"; MAXTYPE="$Y"; fi; done; printf '{"ts":%s,"battery_tenth_c":"%s","max_zone_millideg_c":%s,"max_zone_type":"%s"}\n' "$TS" "$BAT" "$MAX" "$MAXTYPE" >> "$SAFETY_LOG"; if [ -n "$BAT" ] && [ "$BAT" -ge 460 ]; then touch "$STOP" "$ROOT"/STOP_p13h_*; exit 0; fi; if [ "$MAX" -ge 92000 ]; then touch "$STOP" "$ROOT"/STOP_p13h_*; exit 0; fi; sleep 30; done; }
run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; printf '{"schema_version":"phase13_p13h_chain_event_v1","step":"%s","status":"stopped","returncode":130,"updated_at_epoch":%s}\n' "$STEP" "$(date +%s)" >> "$EVENTS"; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; printf '{"schema_version":"phase13_p13h_chain_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\n' "$STEP" "$STATUS" "$RC" "$(date +%s)" >> "$EVENTS"; if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }
rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP" "$SAFETY_LOG" "$STOP"
rm -f "$ROOT"/STOP_p13h_baseline_eval "$ROOT"/STOP_p13h_train "$ROOT"/STOP_p13h_trained_eval
mkdir -p "$ROOT/runs"
write_state running preflight
thermal_monitor & MONITOR_PID=$!
run_step g1_layer0_opencl_smoke "$LAYER_RUNNER" --run-opencl /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 "$ROOT/preflight/g1_layer0_opencl_smoke"
run_step g3_two_layer_opencl_stack_smoke "$LAYER_RUNNER" --run-opencl-stack /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer1_seq128_v0 "$ROOT/preflight/g3_two_layer_opencl_stack_smoke"
run_step baseline_eval sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h; /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/bin/phase11_runner --queue queue/p13h_baseline_eval_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_baseline_eval_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_baseline_eval_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/STOP_p13h_baseline_eval'
run_step train sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h; /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/bin/phase11_runner --queue queue/p13h_train_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_train_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_train_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/STOP_p13h_train'
run_step trained_eval sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h; /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/bin/phase11_runner --queue queue/p13h_trained_eval_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_trained_eval_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/p13h_trained_eval_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/STOP_p13h_trained_eval'
kill "$MONITOR_PID" 2>/dev/null || true
write_state completed done
exit 0
