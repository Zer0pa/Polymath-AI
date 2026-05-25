# Orchestrator POV: Phase 13 To Phase 14 Drift Cleanup

Document Class: ORCHESTRATOR_POV
Created: 2026-05-25T16:13:19Z
Repository: /Users/Zer0pa/Polymat AI/Polymath-AI
Branch observed on Mac: gemma4-megakernel-native-training
Authority runtime: REDMAGIC NX789J / SM8750 / FY25013101C8
RunPod pod: ltg8fdnxgmzwjy

## Short Verdict

Phase 13 made real progress against the earlier drift, but it did not prove the
governing objective. It corrected the worst contamination failure by forcing
Gemma identity checks, scaled the phone-native corpus beyond toy size, added a
second Gemma-compatible residual adapter site, and kept the HTP lane from being
misrepresented as heterogeneous learning.

The run still failed the top gate. The phone-local long run stopped at 1742 of
5000 updates after thermal safety signals, and full-heldout evaluation did not
produce a promotable before/after learning result. The active training path was
Adreno/OpenCL residual-adapter training with a fallback label-contrastive
objective, not full Gemma teacher distillation, not HTP training, not full
Gemma4 training, and not a fused megakernel.

My recommendation: do not continue as if Phase 13 is a partial pass. Start
Phase 14 with control-plane cleanup, artifact quarantine, and exact-state
reconciliation. Only then repair the heldout/objective/thermal failure and
rerun a scaled phone-local campaign.

## Non-Technical POV For The User

The last agent did some useful work. It stopped using the obviously wrong
Qwen-shaped artifacts as proof for Gemma, made the system identify Gemma assets
before training, and got the phone to build a real dataset cache instead of a
tiny sample.

But it did not prove the big thing. It ran a long phone job, the phone got into
a safety-risk temperature zone, the job stopped early, and the final heldout
test never gave us a clean "the model got better on unseen data" result.

So the situation is: less bullshit than before, but not success. The next move
is not to widen claims. The next move is to clean the workspace, line up the
Mac, phone, RunPod, git branch, and GPD state, then run the next experiment from
a clean authority metric.

Use a new orchestrator, or the same agent only if it is reloaded through the
startup prompt and forced to begin with cleanup. I would prefer a new
orchestrator because the system has accumulated state drift and stale claims in
multiple places.

## What Phase 13 Actually Advanced

- P13-A contamination audit passed. Phase 12 Qwen/random-init hidden-size-1536
  artifacts were quarantined as negative tool-surface probes and forbidden from
  promoted Gemma gates.
- P13-B identity and kernel-lineage checks passed. The phone runner emitted
  `google/gemma-4-E4B`, hidden size `2560`, revision
  `7aa32e6889efd6300124851b164f8b364314c3d8`, and
  `residual_adapter_opencl_training`. A deliberate Qwen hidden-size-1536 config
  was rejected before training.
- P13-C corpus scale passed at the declared floor. The phone built
  `8192` train and `1024` heldout seq128 caches from
  `databricks/databricks-dolly-15k` with phone-side Gemma tokenization and
  RunPod tokenizer parity spot checks.
- P13-D gradient parity passed for 64 seeded finite-difference residual-adapter
  coordinates across rank16/rank32 and init/final states.
- P13-E added a second Gemma-compatible post-layer1 rank16 residual adapter
  site with phone-side forward/backward/update evidence and 8 sampled
  finite-difference checks.
- P13-F produced a Gemma hidden-size-2560 HTP ReLU tensor island that executed
  on phone. This is useful hardware-surface evidence only.
- P13-G correctly selected Adreno/OpenCL fallback because no HTP tensor was
  consumed by the Gemma training loop.
- P13-I wrote exact claims and did not promote P13-H.

## What Phase 13 Failed To Prove

- No full Gemma4 training.
- No full-Gemma teacher top-k distillation in P13-H.
- No HTP backprop, HTP optimizer, updateable HTP tensor, or HTP-to-Adreno
  learning bridge.
- No integrated heterogeneous Gemma learning.
- No broad capability or benchmark readiness.
- No fused/static megakernel training claim.
- No accepted long-horizon heldout learning result.

## Hard Blockers Seen In The Current Evidence

1. P13-H failed. It reached `1742 / 5000` updates, then stopped under thermal
   safety conditions. The gate result reports `cpu-1-0-1` at `95 C` and
   `alps-therm` at `130.048 C`.
2. Full-heldout baseline and trained eval did not complete as accepted gates.
   P13-H therefore has no promotable heldout KL improvement.
3. The P13-H objective was
   `label_contrastive_topk_kl_v1` with teacher provenance
   `phone_native_p13c_labels_to_host_deterministic_onehot_topk_precompute`.
   That is a fallback objective, not full Gemma teacher distillation.
4. HTP remains disconnected from learning. The HTP artifact is a ReLU island,
   not a consumed teacher, backward pass, optimizer path, or updateable context.
5. Artifact hygiene is not clean. The untracked Phase 13 report tree contains
   raw HTP payloads:
   `P13-G-heterogeneous-vs-adreno-baseline/phone_htp_relu_benchmark/run_*/Result_0/gemma_hidden_relu_out.raw`.
   These must not be committed. Hash and quarantine or delete only after the
   next orchestrator verifies the manifests.
6. GPD state is stale and internally inconsistent. `.gpd/STATE.md` still says
   Phase 13 is in progress and P13-H is ready, while P13-H has failed and P13-I
   has written exact claims. `.gpd/state.json` also contains contradictory P13-F
   entries: one saying P13-F falsified, another saying it passed as a narrow HTP
   ReLU island.
7. The Mac worktree is dirty with source changes, GPD files, Phase 12/13
   reports, and Phase 13 scripts. This is expected after execution, but it must
   be classified before any commit.
8. Live ADB inspection from this session saw no phone device. The next
   orchestrator must not assume the phone is connected until `adb devices -l`
   shows it.
9. Live RunPod inspection found `/workspace/Polymath-AI` on branch
   `linux/phase0g-qairt-v2.43`, not `gemma4-megakernel-native-training`, with a
   dirty/untracked tree. RunPod must be reconciled before being used as a build
   or oracle source.

## Worktree Cleanup Mandate

Phase 14 must begin with a cleanup gate before experiments:

1. Snapshot Mac git status, RunPod git status, phone device state, and phase
   report payload inventory.
2. Classify every modified or untracked file as:
   `source_change`, `small_report_allowed`, `state_doc`, `script_allowed`,
   `generated_payload_forbidden`, `build_cache_forbidden`, or `unknown`.
3. Do not commit raw `.raw`, `.bin`, `.safetensors`, `.pt`, `.npy`, model
   weights, QNN/DLC payloads, SDK binaries, token files, env files, `.venv`,
   `node_modules`, or build caches.
4. Repair `.gpd/STATE.md`, `.gpd/state.json`, `.gpd/ROADMAP.md`, and
   `.gpd/runlog.jsonl` so they say exactly:
   - Phase 13 P13-A through P13-G produced narrow artifacts.
   - P13-H failed.
   - P13-I exact claims were written.
   - Next branch is Phase 14: repair scaled heldout learning before new
     hardware claims.
5. Reconcile Mac and RunPod branches. RunPod must not silently act from the
   stale `linux/phase0g-qairt-v2.43` branch for Gemma4 Phase 14.
6. Only after cleanup should the orchestrator design or launch a new phone run.

## Phase 14 Engineering Direction

The next phase should not start with "try another overnight run." It should
repair the experiment so an overnight run can mean something.

Required Phase 14 gates:

- P14-0: Worktree and control-plane cleanup.
- P14-1: Phone reconnection and thermal baseline. If the phone is disconnected,
  stop at setup instructions rather than inventing evidence.
- P14-2: Artifact quarantine and compact manifest repair for Phase 13 raw
  payloads.
- P14-3: State reconciliation across GPD, AGENTS, Mac, RunPod, and GitHub.
- P14-4: Heldout evaluator repair. Full-heldout baseline and trained eval must
  run independently before another long campaign.
- P14-5: Objective repair. Prefer full Gemma teacher top-k/logit-KL shards or a
  clearly stronger Gemma-derived objective over label-onehot fallback. If full
  teacher shards are too expensive, prove that boundary and select a stronger
  approximation with falsifiers.
- P14-6: Thermal strategy. Use reversible Android/RedMagic-safe controls only;
  no fridge, freezer, ice, or condensation-adjacent cooling. Segment long runs
  into thermally bounded stages if needed.
- P14-7: Short learning run with full-heldout before/after proof.
- P14-8: Only then launch a disconnected long phone-local sequence.

## Same Agent Or New Agent

The same agent can continue only if it starts from this document and the Phase
14 startup prompt, and only if it treats cleanup as gate zero. It did resolve
some Gemma drift, but it also left stale control-plane state and raw payloads in
the untracked report tree. That is exactly how future agents drift.

Preferred route: start a new high-reasoning orchestrator. Its first job is not
training. Its first job is to make the current evidence, source tree, and remote
state coherent enough that the next training run has scientific meaning.
