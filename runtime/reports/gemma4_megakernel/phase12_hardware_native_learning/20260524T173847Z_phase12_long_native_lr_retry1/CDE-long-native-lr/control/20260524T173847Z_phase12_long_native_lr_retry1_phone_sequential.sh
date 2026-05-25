#!/system/bin/sh
set -u
ROOT=/data/local/tmp/polymath_gemma4_gate/phase12
BIN="$ROOT/bin/phase11_runner"
RUN_ID=20260524T173847Z_phase12_long_native_lr_retry1
DONE="$ROOT/${RUN_ID}_done.json"
rm -f "$DONE"
cd "$ROOT"
rm -f /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train_state.json /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train_heartbeat.json /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train
"$BIN" --queue queue/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train
rc=$?
if [ "$rc" -ne 0 ]; then echo '{"status": "fail", "failed_run_id": "20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_train"}' > "$DONE"; exit "$rc"; fi
rm -f /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval_state.json /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval_heartbeat.json /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval
"$BIN" --queue queue/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval
rc=$?
if [ "$rc" -ne 0 ]; then echo '{"status": "fail", "failed_run_id": "20260524T173847Z_phase12_long_native_lr_retry1_lr3e4_cont24_eval"}' > "$DONE"; exit "$rc"; fi
rm -f /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train_state.json /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train_heartbeat.json /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train
"$BIN" --queue queue/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train
rc=$?
if [ "$rc" -ne 0 ]; then echo '{"status": "fail", "failed_run_id": "20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_train"}' > "$DONE"; exit "$rc"; fi
rm -f /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval_state.json /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval_heartbeat.json /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval
"$BIN" --queue queue/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval_queue.jsonl --run-root runs --heartbeat /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval_heartbeat.json --state /data/local/tmp/polymath_gemma4_gate/phase12/20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval_state.json --stop-file /data/local/tmp/polymath_gemma4_gate/phase12/STOP_20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval
rc=$?
if [ "$rc" -ne 0 ]; then echo '{"status": "fail", "failed_run_id": "20260524T173847Z_phase12_long_native_lr_retry1_lr1e4_cont24_eval"}' > "$DONE"; exit "$rc"; fi
echo '{"status": "pass", "run_id": "20260524T173847Z_phase12_long_native_lr_retry1"}' > "$DONE"
