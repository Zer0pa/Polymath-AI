#!/system/bin/sh
set -u
ROOT=/data/local/tmp/polymath_gemma4_gate/phase11
RUN_ID=20260523T225149Z_h11h_combined_povc
RUNNER=/data/local/tmp/polymath_gemma4_gate/phase11/phase11_runner
LAYER_RUNNER=/data/local/tmp/polymath_gemma4_gate/phase11/gemma4_layer_runner
REGRESSION_ROOT=/data/local/tmp/polymath_gemma4_gate/phase11/runs/20260523T225149Z_h11h_combined_povc_phone_regressions
LOG="$ROOT/h11h_${RUN_ID}_chain.log"
EVENTS="$ROOT/h11h_${RUN_ID}_chain_events.jsonl"
STATE="$ROOT/h11h_${RUN_ID}_chain_state.json"
STOP="$ROOT/STOP_h11h_chain_${RUN_ID}"
BOOTSTRAP="$ROOT/h11h_${RUN_ID}_chain.bootstrap.log"
write_state() { printf '{"schema_version":"phase11_h11h_detached_chain_state_v1","run_id":"%s","status":"%s","step":"%s","updated_at_epoch":%s}\n' "$RUN_ID" "$1" "$2" "$(date +%s)" > "$STATE"; }
run_step() { STEP="$1"; shift; if [ -f "$STOP" ]; then write_state stopped "$STEP"; printf '{"schema_version":"phase11_h11h_detached_chain_event_v1","step":"$STEP","status":"stopped","returncode":%s,"updated_at_epoch":%s}\n' 130 "$(date +%s)" >> "$EVENTS"; exit 130; fi; write_state running "$STEP"; "$@" >> "$LOG" 2>&1; RC="$?"; if [ "$RC" -eq 0 ]; then STATUS=pass; else STATUS=fail; fi; printf '{"schema_version":"phase11_h11h_detached_chain_event_v1","step":"%s","status":"%s","returncode":%s,"updated_at_epoch":%s}\n' "$STEP" "$STATUS" "$RC" "$(date +%s)" >> "$EVENTS"; if [ "$RC" -ne 0 ]; then write_state failed "$STEP"; exit "$RC"; fi; }
rm -f "$EVENTS" "$LOG" "$STATE" "$BOOTSTRAP"
rm -f "$ROOT"/STOP_h11h_baseline_eval "$ROOT"/STOP_h11h_train "$ROOT"/STOP_h11h_trained_eval "$STOP"
rm -rf /data/local/tmp/polymath_gemma4_gate/phase11/runs/20260523T225149Z_h11h_combined_povc_phone_regressions /data/local/tmp/polymath_gemma4_gate/phase11/runs/20260523T225149Z_h11h_combined_povc_baseline_eval /data/local/tmp/polymath_gemma4_gate/phase11/runs/20260523T225149Z_h11h_combined_povc_train /data/local/tmp/polymath_gemma4_gate/phase11/runs/20260523T225149Z_h11h_combined_povc_trained_eval
mkdir -p "$REGRESSION_ROOT" "$ROOT/runs"
write_state running preflight
run_step g1_layer0_opencl_smoke "$LAYER_RUNNER" --run-opencl /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 "$REGRESSION_ROOT/g1_layer0_opencl_smoke"
run_step g3_two_layer_opencl_stack_smoke "$LAYER_RUNNER" --run-opencl-stack /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer1_seq128_v0 "$REGRESSION_ROOT/g3_two_layer_opencl_stack_smoke"
run_step g8_rank4_distill_compact_smoke "$LAYER_RUNNER" --run-g8-distill-compact-rank /data/local/tmp/polymath_gemma4_gate/hf_stream/20260517T083219Z_phase10_hf_auth_token_bridge_baseline_cache /data/local/tmp/polymath_gemma4_gate/streamed_assets/g8_layer01_20260517T071405Z /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer1_seq128_v0 /data/local/tmp/polymath_gemma4_gate/adapter_training/g5g6_rank4_20260517T040000Z/checkpoint "$REGRESSION_ROOT/g8_rank4_distill_compact_smoke" 0.01 4
run_step baseline_eval sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase11; /data/local/tmp/polymath_gemma4_gate/phase11/phase11_runner --queue queue/h11h_baseline_eval_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase11/h11h_baseline_eval_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase11/h11h_baseline_eval_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase11/STOP_h11h_baseline_eval'
run_step train sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase11; /data/local/tmp/polymath_gemma4_gate/phase11/phase11_runner --queue queue/h11h_train_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase11/h11h_train_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase11/h11h_train_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase11/STOP_h11h_train'
run_step trained_eval sh -c 'cd /data/local/tmp/polymath_gemma4_gate/phase11; /data/local/tmp/polymath_gemma4_gate/phase11/phase11_runner --queue queue/h11h_trained_eval_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase11/h11h_trained_eval_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase11/h11h_trained_eval_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase11/STOP_h11h_trained_eval'
write_state completed done
exit 0
