#!/system/bin/sh
set -u
ROOT=/data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval
RUN_ID=p14_full_heldout_eval_20260525T171624Z
RUNNER=/data/local/tmp/polymath_gemma4_gate/bin/phase11_runner
SAFETY_LOG=/data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/p14_p14_full_heldout_eval_20260525T171624Z_safety.jsonl
LOG="$ROOT/p14_${RUN_ID}_full_heldout_eval.log"
EVENTS="$ROOT/p14_${RUN_ID}_full_heldout_eval_events.jsonl"
STATE="$ROOT/p14_${RUN_ID}_full_heldout_eval_state.json"
STOP="$ROOT/STOP_p14_full_heldout_eval_${RUN_ID}"
BOOTSTRAP="$ROOT/p14_${RUN_ID}_full_heldout_eval.bootstrap.log"
write_state() { printf '{"schema_version":"phase14_full_heldout_eval_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\n' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }
write_event() { printf '{"schema_version":"phase14_full_heldout_eval_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\n' "$1" "$2" "$3" "$(date +%s)" >> "$EVENTS"; }
thermal_monitor() { while true; do TS="$(date +%s)"; BAT="$(dumpsys battery 2>/dev/null | awk '/temperature:/ {print $2; exit}')"; MAX=0; MAXTYPE=unknown; for z in /sys/class/thermal/thermal_zone*; do [ -r "$z/temp" ] || continue; T="$(cat "$z/temp" 2>/dev/null)"; Y="$(cat "$z/type" 2>/dev/null)"; case "$T" in -*) continue;; ""|*[!0-9]*) continue;; esac; if [ "$T" -gt "$MAX" ]; then MAX="$T"; MAXTYPE="$Y"; fi; done; printf '{"ts":%s,"battery_tenth_c":"%s","max_zone_millideg_c":%s,"max_zone_type":"%s"}\n' "$TS" "$BAT" "$MAX" "$MAXTYPE" >> "$SAFETY_LOG"; if [ -n "$BAT" ] && [ "$BAT" -ge 380 ]; then touch "$STOP" "$ROOT"/STOP_p14_*; exit 0; fi; if [ "$MAX" -ge 85000 ]; then touch "$STOP" "$ROOT"/STOP_p14_*; exit 0; fi; sleep 30; done; }
require_checkpoint() { if [ ! -f "$1/manifest.json" ]; then write_state failed "missing_checkpoint_$2"; write_event "missing_checkpoint_$2" fail 2; exit 2; fi; }
run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; write_event "$STEP" stopped 130; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; write_event "$STEP" "$STATUS" "$RC"; if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }
rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP" "$SAFETY_LOG" "$STOP"
rm -f "$ROOT"/STOP_p14_baseline "$ROOT"/STOP_p14_candidate "$ROOT"/STOP_p14_*
mkdir -p "$ROOT/runs"
require_checkpoint /data/local/tmp/polymath_gemma4_gate/phase12/runs/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train/Phase12-long-native-lr/iterations/iter_000023/checkpoint baseline
require_checkpoint /data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13h/runs/20260524T210920Z_phase13_gemma4_only_heterogeneous_p13h_20260524T232423Z_train/P13-H-overnight-phone-local-long-run/iterations/iter_001741/checkpoint candidate
thermal_monitor & MONITOR_PID=$!
run_step baseline sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval; /data/local/tmp/polymath_gemma4_gate/bin/phase11_runner --queue queue/p14_baseline_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/p14_baseline_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/p14_baseline_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/STOP_p14_baseline'
run_step candidate sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval; /data/local/tmp/polymath_gemma4_gate/bin/phase11_runner --queue queue/p14_candidate_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/p14_candidate_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/p14_candidate_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase14/p14_full_heldout_eval/STOP_p14_candidate'
kill "$MONITOR_PID" 2>/dev/null || true
write_state completed done
exit 0
