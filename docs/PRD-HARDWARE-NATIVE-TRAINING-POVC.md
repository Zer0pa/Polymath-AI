# PRD: Phase 11 Hardware-Native Training POVC

Document Class: AUTHORITY_PRD
Phase: 11
Status: READY_FOR_EXECUTION_AGENT
Created: 2026-05-23
Repository: https://github.com/Zer0pa/Polymath-AI
Branch: gemma4-megakernel-native-training
Authority runtime: REDMAGIC NX789J / SM8750 / serial FY25013101C8
RunPod oracle: pod ltg8fdnxgmzwjy at /workspace/Polymath-AI
RunPod SSH primary: ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519
RunPod SSH alternate: ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519
Phone root: /data/local/tmp/polymath_gemma4_gate
Doctrine: RESISTANCE-V2.md

## 1. Objective

Phase 11 turns the current narrow but real Gemma 4 phone-training lane into a
hardware-native proof-of-valuable-compute campaign. The campaign is not a
training run yet; it is the control artifact for the next execution agent.

The top gate is:

```text
Run a phone-native sequential experiment campaign that removes host
per-iteration orchestration, explains the 36.7 s/iteration dead time, tests
safe performance controls, probes OpenCL recordable queues, lifts the trainable
scope above the current rank-4 floor, replaces parity-MSE with a capability
objective, investigates QAIRT mutable-adapter/zero-order HTP use, and combines
the winning choices into one phone-resident run with non-regressing authority
gates and a falsifier report.
```

No documentation artifact counts as progress toward that gate. Only phone
experiments, machine-readable gate results, checksums, manifests, and falsifier
reports count.

## 2. Ground Truth

Passed and preserved:

- G1 E4B layer0 OpenCL phone parity passed.
- G3 two-layer OpenCL forward passed.
- G5 rank-4 adapter backward passed.
- G6 phone-side SGD update passed.
- G7 HF stream/tokenize/pack path passed.
- G8 repaired integrated training passed.
- G9 narrow sustained chain passed.
- Phase 10 six-hour endurance passed for the narrow rank-4 two-layer lane.

Blocked nonclaims:

- Full Gemma4 training is not proven.
- Hexagon NPU training is not proven.
- Public benchmark readiness is not proven.
- Theoretical maximum is not proven.

New research findings controlling Phase 11:

- The 21.3 percent active-training ratio is likely host orchestration plus OEM
  perf/thermal mitigation, not a silicon limit.
- The current rank-4 post-layer0 residual adapter has only 10240 fp32 trainable
  params and is below a capability-moving plasticity floor.
- QAIRT 2.44 LoRA/updateable-section tooling is installed on phone and RunPod;
  QnnContext_applyBinarySection is a real mutable-section primitive.
- OpenCL remains the near-term route, but cl_qcom_recordable_queues must be
  probed and used if available.
- A long-lived phone daemon plus recordable queues is the near-term
  megakernel-equivalent; a persistent GPU megakernel is not the near-term
  Adreno/KGSL abstraction.

## 3. Boundary Rules

The phone is the authority runtime. The Mac starts, inspects, and pulls
artifacts. RunPod builds, compiles, and provides references. Neither Mac nor
RunPod may drive every iteration, serve runtime minibatches, compute gradients,
or run optimizer updates for an authority phone-training claim.

True boundary blockers only:

- Missing credentials or hardware after diagnosis.
- Legal or license ambiguity.
- Destructive phone risk without rollback.
- Uncontrolled cloud spend.
- Architectural contradiction.

All other failures are data. The sequence continues unless the failure blocks a
later gate by physics, safety, or topology.

## 4. Long-Horizon Operating Mode

The executor is expected to run this as a campaign, not as a single result
followed by a report. After each gate, it must make a decision and continue:

- pass: freeze the winning config, record exact evidence, and advance;
- fail: record exact blocker/evidence, select the strongest valid fallback,
  and advance when topology and safety permit;
- blocked: distinguish true external blocker from engineering task, then either
  repair, run a bounded research/falsification subtask, or preserve the blocker
  and advance with a declared fallback.

Intermediate reporting is not a deliverable. The executor may stop early only
for a safety stop, missing authority hardware after diagnosis, credentials that
cannot be recovered without operator action, legal/license ambiguity,
uncontrolled spend, or an architectural contradiction that invalidates the PRD.

If subagents or research tools are available, they are used only for concrete
blockers and falsification questions with a required decision output:
`repair now`, `run fallback`, `drop hypothesis`, or `escalate true blocker`.
Broad literature dumps do not count.

## 5. Phone-Resident Runner Contract

Phase 11 requires a phone-resident sequential runner before any long campaign.
The runner is the campaign control plane on the phone.

Required phone layout:

```text
/data/local/tmp/polymath_gemma4_gate/phase11/
  queue/phase11_queue.jsonl
  runner.pid
  runner_state.json
  heartbeat.json
  STOP
  runs/<run_id>/
    campaign_manifest.json
    checksum_chain.jsonl
    H11-A-daemon/
    H11-B-perf-envelope/
    H11-C-bottleneck-autopsy/
    H11-D-recordable-queues/
    H11-E-scope-sweep/
    H11-F-objective-upgrade/
    H11-G-htp-mutable-adapter/
    H11-H-combined-povc/
```

Queue records are JSONL. Minimum fields:

```json
{"id":"H11-A-001","gate":"H11-A","config":"configs/H11-A.json","depends_on":[],"resume":"auto"}
```

Runner requirements:

- Starts once from ADB, then executes the local queue without ADB per
  iteration.
- Keeps OpenCL context, mmaped weights, layer packs, tokenizer state, and
  checkpoint store alive when the experiment permits it.
- Writes heartbeat.json at least every 30 seconds with gate id, step, pid,
  monotonic timestamp, storage free, RSS, thermal summary, and last artifact
  hash.
- Honors a local STOP file before starting the next unit of work and at each
  safe checkpoint boundary.
- On resume, reads runner_state.json and checksum_chain.jsonl, skips completed
  passing gates, resumes incomplete gates if the gate declares resume safe, and
  never overwrites prior evidence.
- Maintains a checksum chain: each artifact hash record includes the previous
  chain hash, artifact path, sha256, byte count, timestamp, gate id, and runner
  build id.
- Emits one run directory per gate with gate_result.json, timing_breakdown.json,
  telemetry.jsonl, artifact_manifest.json, falsifier_report.md, blockers.md,
  and sanitized commands.log.
- Prints no secrets. Token values, SDK binaries, model weights, raw large
  tensors, and env files stay out of git.
- Allows the phone to continue after USB or ADB disconnect if Android permits
  the process to survive. If the OS kills it, that is evidence for H11-A and
  must be recorded exactly.

Canonical start shape for the future executor:

```bash
adb -s FY25013101C8 shell 'cd /data/local/tmp/polymath_gemma4_gate/phase11 && nohup ./phase11_runner --queue queue/phase11_queue.jsonl --run-root runs --heartbeat heartbeat.json --state runner_state.json > runner.log 2>&1 & echo $! > runner.pid'
```

## 6. Safety Stops

Default stops for H11-B onward:

- Android thermal status >= 3.
- Battery temperature >= 46 C for more than 120 seconds.
- Skin temperature >= 50 C for more than 120 seconds.
- SoC die status severe or a reported socd temperature >= 92 C.
- GPU or CPU cooling device state remains above 0 for more than 300 seconds
  during a gate that claims unmitigated performance mode.
- Free space under the phone root falls below 8 GiB.
- Runner RSS exceeds 18 GiB or grows by more than 1 GiB over 30 minutes without
  a declared cache allocation.
- Any checkpoint, adapter, or manifest checksum mismatch.
- G1 or G3 regression fails after a material runtime change.
- Three runner crashes in one gate.

No fridge, ice, freezer, or condensation-adjacent cooling is allowed. A sealed,
dry, monitored protocol would require a separate written safety design and
operator approval before use. It is not part of this PRD.

## 7. Sequential Campaign

Run H11-A through H11-H in order. A failed gate records why it failed and the
sequence continues with the best valid fallback unless a true boundary blocker
exists.

### H11-A: Phone-Resident Daemon

- Hypothesis: Replacing per-iteration ADB/process restart with a long-lived
  phone process and local queue will materially raise active-training/wall
  ratio and allow disconnected execution after queue start.
- Action: Implement daemon/queue mode while preserving the existing one-shot
  runner as fallback. Measure cold-start, one-shot iteration, daemon iteration,
  and a 50-iteration narrow-lane run. Run a disconnect test after queue start.
- Pass condition: Daemon mode completes at least 50 chained narrow-lane
  iterations, preserves checkpoint chaining, keeps G1/G3/G8 relevant samples
  green, reaches active/wall >= 0.50 or >= 2x Phase 10 baseline, and keeps
  running after a 10-minute ADB disconnect if Android permits.
- Fail condition: Runner cannot keep state across iterations, loses checkpoint
  continuity, depends on host per iteration, fails non-regression, or is killed
  on disconnect with no recoverable resume path.
- Artifacts: daemon design note, queue schema, runner build id, cold-start
  timing, one-shot vs daemon timing, disconnect log, heartbeat series,
  checksum_chain.jsonl, gate_result.json.
- Falsifiers: hidden ADB iteration driver, process restart per step, missing
  heartbeat, overwritten artifacts, host-side minibatch serving, stale
  checkpoint input.
- Next on pass: Freeze daemon as the Phase 11 runner and run H11-B under it.
- Next on fail: Keep one-shot path only for diagnostics, record the exact OS or
  runner blocker, and run H11-B with attached execution while preserving the
  failure as a blocker for H11-H disconnect-safe promotion.

### H11-B: Performance Envelope

- Hypothesis: The Phase 10 active/wall limit is partly OEM perf/thermal
  mitigation, and safe fixed-performance/fan/charge separation settings can
  improve sustained work without unsafe device treatment.
- Action: Probe fixed performance mode, stay-awake USB, low-power state,
  fan/charge-separation status, thermal mode properties, cooling_device states,
  KGSL gpubusy, CPU cluster frequencies, battery/skin/SoC temperatures, and OEM
  perf services. Apply only reversible no-root controls first.
- Pass condition: A declared safe profile is recorded, reversible, respects the
  stop thresholds, and improves H11-A daemon active/wall or sustained active
  seconds by >= 15 percent without G1/G3/G8 regression.
- Fail condition: Controls are unavailable, not reversible, unsafe, ineffective,
  or induce throttling/checkpoint/correctness regression.
- Artifacts: pre/post device manifest, exact commands, thermal/cooling/frequency
  telemetry, fan/charge-separation observation, profile decision,
  gate_result.json.
- Falsifiers: Android thermal_status 0 masking kernel cooling states, battery
  heating from charging, GameSpace/Diablo claims without telemetry, hidden root
  dependence, unsafe cooling.
- Next on pass: Use the safe profile as the default for H11-C and later.
- Next on fail: Revert settings, keep the safest baseline profile, and proceed
  to H11-C to quantify bottlenecks without claiming perf unlock.

### H11-C: Bottleneck Autopsy

- Hypothesis: The 36.7 s/iteration dead time can be decomposed into compute,
  launch, tokenization, checkpoint, validation, storage, network, and
  orchestration components.
- Action: Instrument both one-shot and daemon modes with monotonic timers for
  cold start, OpenCL context creation, kernel compile/cache, tokenization,
  token-to-hidden, layer forward, backward/update, checkpoint write/fsync,
  validation sampling, network fetch, storage reads/writes, host pull, and idle
  waits. Run a controlled 30-iteration narrow-lane autopsy.
- Pass condition: timing_breakdown.json accounts for >= 90 percent of wall time
  or leaves residual < 5 s/iteration, identifies the dominant dead-time source,
  and explains the Phase 10 36.7 s/iteration gap with evidence.
- Fail condition: timers are missing, residual remains >= 10 percent without
  explanation, or the result cannot distinguish compute from orchestration.
- Artifacts: timing schema, per-iteration timing_breakdown.jsonl, summary
  budget, residual analysis, gate_result.json.
- Falsifiers: profiler overhead changing behavior, amortized RunPod oracle cost
  misattributed, validation cadence hidden, checkpoint fsync omitted, idle sleep
  treated as compute.
- Next on pass: Choose H11-D integration priority from the measured bottleneck.
- Next on fail: Add missing timers and rerun once; if still unresolved, freeze
  the unknown residual as a blocker and continue with H11-D probe only.

### H11-D: OpenCL Recordable Queues

- Hypothesis: cl_qcom_recordable_queues is available on Adreno 830 and can
  reduce repeated launch overhead in the phone daemon.
- Action: Probe OpenCL platform/device extensions and function pointers. If
  supported, benchmark no-op, fixed-arg, and mutable-arg recorded sequences
  against ordinary enqueue. Integrate only the narrow sequence that preserves
  correctness and matches H11-C bottleneck evidence.
- Pass condition: Exact support is recorded; if supported, recorded queues pass
  correctness and improve measured launch or end-to-end gate time without
  changing tensor outputs. If unsupported, the exact device/driver result is
  recorded and the campaign continues without it.
- Fail condition: Probe is inconclusive, function pointers are assumed, outputs
  drift, or integration adds complexity without measured benefit.
- Artifacts: extension dump, symbol probe, microbenchmark JSON, A/B timing,
  output comparison, gate_result.json.
- Falsifiers: emulator or wrong device probe, CPU fallback, ordinary queue path
  mislabeled recordable, launch microbenchmark promoted despite no end-to-end
  relevance.
- Next on pass: Keep recordable queues enabled only where useful.
- Next on fail: Disable recordable queues by default and proceed to H11-E with
  the daemon/perf profile.

### H11-E: Trainable Scope Sweep

- Hypothesis: The current rank-4 post-layer0 residual adapter is below the
  capability-moving floor; larger and better-placed DoRA/LoRA scopes will
  produce stronger loss/capability signal while fitting phone memory.
- Action: Compare current rank-4 scope against at least two expanded scopes,
  including DoRA or LoRA r=16+ across q_proj, o_proj, gate_proj, up_proj in
  later blocks when feasible. For each scope, measure memory, active time,
  gradient correctness, checkpoint size, loss movement, and first capability
  signal.
- Pass condition: One scope is selected by evidence: finite gradients,
  non-regressing G1/G3 and relevant G8 checks, frozen hashes stable, checkpoint
  replay valid, memory within stop thresholds, and better objective/capability
  signal per wall or active second than rank-4 baseline.
- Fail condition: Expanded scopes fail memory, gradient parity, checkpoint
  replay, or show no better signal than rank-4.
- Artifacts: scope configs, parameter counts, memory budget, gradient reports,
  active/wall telemetry, checkpoint manifests, loss/capability comparison,
  gate_result.json.
- Falsifiers: parameter-count inflation without placement value, hidden host
  backward, relaxed gradient tolerances, frozen base mutation, rank sweep judged
  on speed only.
- Next on pass: Carry the selected scope into H11-F.
- Next on fail: Keep the largest correct scope as substrate, record why it does
  not cross the plasticity floor, and continue H11-F with a reduced objective
  test only.

### H11-F: Objective Upgrade

- Hypothesis: Parity-MSE validates mechanics but is not a training objective;
  logit-KL distillation or another capability-relevant objective is required to
  move useful behavior.
- Action: Replace parity-MSE as the promoted training objective. First
  candidate: top-k logit-KL distillation against a frozen Gemma/HTP teacher or
  a precomputed teacher shard. Define the first capability-moving metric before
  the run: teacher-agreement improvement on held-out shard plus IFEval-mini or
  domain instruction-format mini-eval.
- Pass condition: On the H11-E selected scope, a 100+ iteration phone run shows
  train KL decrease, held-out KL or perplexity not worse than baseline, and the
  declared first capability metric improves beyond a fixed-adapter control.
- Fail condition: KL is unstable, held-out signal regresses, metric does not
  move beyond control, or objective requires host runtime service.
- Artifacts: objective spec, teacher-shard manifest, metric definition,
  baseline/control report, loss traces, held-out report, mini-eval report,
  gate_result.json.
- Falsifiers: parity-MSE renamed as objective, teacher generated during phone
  runtime by RunPod, train-only loss overfit sold as capability, metric chosen
  after results.
- Next on pass: Carry the objective and metric into H11-G and H11-H.
- Next on fail: Try one predeclared fallback objective or reduce scope; if it
  still fails, H11-H may only claim systems progress, not capability movement.

### H11-G: HTP Mutable-Adapter / Zero-Order Arm

- Hypothesis: QAIRT updateable sections can make HTP a frozen-forward/teacher
  and mutable-adapter or zero-order forward-only training arm, even without a
  public HTP backward API.
- Action: Verify RunPod QAIRT 2.44 env, host compile path, lora_weight_list or
  updateable tensor declaration, qairt-lora-adapter-bin-updater, phone context
  load, QnnContext_applyBinarySection, QnnContext_getBinarySection, and one
  HTP forward after update. Then attempt a bounded SPSA/MeZO-style
  forward-only update on the smallest Gemma-valid updateable adapter that still
  uses real Gemma tensors, fixed controls, and a declared loss. A minimized
  safety probe can de-risk the API path, but it cannot be promoted as training
  progress by itself.
- Pass condition: Host can produce an updateable context or records the exact
  compiler blocker; phone can apply a binary section to a live context and
  verify changed outputs or records the exact API/permission blocker. A zero-
  order arm passes only if loss descends against a fixed control.
- Fail condition: QAIRT path is unavailable, env cannot be repaired, context
  update is not accepted, phone permissions block execution, or MeZO/SPSA does
  not descend.
- Artifacts: QAIRT env report, exact compiler commands, updateable tensor list,
  context utility dump, phone apply log, forward comparison, zero-order trace,
  gate_result.json.
- Falsifiers: HTP inference claimed as training, adapter binary generated on
  host during authority runtime without declaration, unverified symbol
  assumption, normal backprop claimed on HTP without a proven API.
- Next on pass: Treat HTP as teacher/frozen-forward/updateable-section arm in
  H11-H if it improves the campaign; do not call it normal HTP backprop.
- Next on fail: Keep HTP out of the combined path, preserve the exact blocker,
  and run H11-H with OpenCL daemon/perf/scope/objective choices.

### H11-H: Combined POVC Run

- Hypothesis: Combining the winning daemon, performance profile, queue backend,
  trainable scope, objective, and optional HTP role will produce a phone-native
  run that is materially closer to useful Gemma4 training than the Phase 10
  rank-4 lane.
- Action: Build one queue-driven phone run using the selected H11-A through
  H11-G choices. Predeclare duration or objective: at least 1000 iterations or
  2 wall-hours, unless the declared capability objective is reached earlier;
  extend toward 6 hours only if stop thresholds stay clear. Rerun G1/G3 and
  relevant G8 regressions before promotion.
- Pass condition: The combined run completes the predeclared objective, keeps
  phone-local runtime topology, reaches active/wall >= 0.50 unless an explicit
  measured bottleneck explains otherwise, preserves G1/G3/relevant G8 gates,
  emits replayable checkpoint/adapter artifacts, and produces a falsifier
  report with no unresolved critical issue.
- Fail condition: Runtime topology regresses to host-driven iterations,
  authority gates regress, artifacts fail replay/checksum, safety stop fires,
  or capability objective fails under the selected scope/objective.
- Artifacts: full queue file, campaign_manifest.json, heartbeat log,
  checksum_chain.jsonl, checkpoint/adapter manifest, loss and metric traces,
  regression reports, falsifier_report.md, gate_result.json.
- Falsifiers: local throughput win replacing objective movement, failed gates
  summarized as success, missing raw artifact hashes, no fixed control,
  benchmark/public-readiness claims without separate gates.
- Next on pass: Promote only the exact combined POVC claim and write the next
  PRD for longer endurance or broader Gemma scope.
- Next on fail: Preserve artifacts, mark the failed hypothesis, select the
  next highest-leverage blocker for Phase 12, and do not write a pass narrative.

## 8. Evidence Policy

Git-allowed:

- Text reports, JSON gate results, manifests, checksums, summaries, schemas,
  source code, and sanitized command logs.

Git-forbidden:

- Model weights, raw large tensor binaries, SDK binaries, .safetensors, .bin
  payloads, .tflite, .litertlm, .task, env files, HF tokens, phone token files,
  SSH keys, node_modules, .venv, and build caches.

Large raw outputs stay on phone or RunPod artifact roots with hashes in git:

- Phone: /data/local/tmp/polymath_gemma4_gate/phase11/runs/<run_id>/
- RunPod: /workspace/artifacts/polymath_gemma4/phase11/<run_id>/

## 9. Promotion Rules

- Phase 11 can promote a phone-resident training POVC only after H11-H passes.
- H11-G can promote HTP only as frozen-forward, teacher, mutable-section, or
  zero-order participation unless normal HTP backprop is proven by API and
  parity evidence.
- H11-E/H11-F can promote a better trainable scope/objective only with
  measured signal and non-regression.
- No Phase 11 artifact promotes full Gemma4 training, public benchmark
  readiness, or theoretical maximum.

## 10. First Executor Action

The next execution agent must read this PRD, then
docs/HANDOFF-HARDWARE-NATIVE-TRAINING-POVC-EXECUTOR.md, then
docs/STARTUP-PROMPT-HARDWARE-NATIVE-TRAINING-POVC.md. It must execute the
campaign, not rewrite the plan, unless a boundary blocker invalidates this PRD.
