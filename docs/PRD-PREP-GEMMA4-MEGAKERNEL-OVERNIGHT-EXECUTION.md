# PRD Prep - Gemma 4 Megakernel Overnight Execution

Date: 2026-05-17
Status: SUPERSEDED_BY_AUTHORITY_PRD
Superseded By: `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
Inputs:
- `/Users/Zer0pa/Polymat AI/orchestrator_brief.md`
- `/Users/Zer0pa/Gemma4 Kernel/docs/orchestrator_handover_gemma4_e4b_gate.md`
- `/Users/Zer0pa/Gemma4 Kernel/gemma4_megakernel/docs/gate_reports/20260516_e4b_layer0_gate_execution.md`
- `RESISTANCE-V2.md`

## New Ground Truth

The first hard phone gate is no longer hypothetical.

Gemma4 Kernel passed a real pretrained `google/gemma-4-E4B` layer 0 forward
gate on REDMAGIC `NX789J / SM8750` through OpenCL:

- p50 FP64 cosine: `0.9999890020383452`
- min FP64 cosine: `0.9999801999737985`
- non-pad tokens: `111`
- failed tokens below `0.99`: `0`
- repeat run: byte-identical output
- upstream gate commit: `c5b6e3522d28d0e1dc56084cb97fa9e95e29aa4e`

This becomes a permanent regression gate, not a terminal success narrative.

## PRD Orientation

The final PRD must not be a plan to reproduce the passed gate. It must be an
overnight execution mandate that starts from the passed gate and drives toward
native phone training.

The real objective is:

```text
End-to-end Gemma 4 training on REDMAGIC SM8750 as a native phone runtime:
HF stream -> phone CPU tokenization -> UFS packed sequence cache -> Adreno/NPU/CPU
training runtime -> validated checkpoint and telemetry artifacts.
```

RunPod remains a build server and PyTorch reference oracle. Mac remains a
control plane. The phone is the runtime.

## Non-Negotiable PRD Character

The PRD must be draconian about outputs, not process theater.

- Agents run end-to-end overnight unless a true boundary blocker appears.
- Blockers become tasks by default.
- Interim reports do not count as progress.
- Host-only success cannot pass a phone gate.
- Phone output cannot pass if it regresses the passed OpenCL layer parity gate.
- Successes are routed through falsification before promotion.
- The PRD must assume agents will shrink, proxy, and narrate; it must prevent that structurally.

True boundary blockers only:

- missing credentials or unreachable required hardware after retry;
- license/legal ambiguity around model weights or training corpora;
- destructive phone risk not covered by rollback;
- uncontrolled cloud spend;
- architectural contradiction that invalidates the gate ladder.

Everything else is an engineering task.

## Required Gate Ladder

The final PRD should mandate at least this ladder:

1. **Regression Preservation**
   - Preserve E4B layer 0 OpenCL phone parity as a required regression.
   - Add artifact hashing and replay command capture.
   - Add intermediate tensor dumps only if they help diagnose future failures.

2. **Forward Expansion**
   - Expand from one layer to a small stack of Gemma layers.
   - Maintain host-reference parity per non-pad token.
   - Reject silent CPU fallback, random weights, shape-only success, or tolerance relaxation.

3. **Kernel Architecture**
   - Refactor the direct OpenCL runner into executor components without changing tensor semantics.
   - Begin fusion only where it preserves the regression gate.
   - Measure dispatch count and memory movement as evidence, not authority.

4. **Backward Path**
   - Implement backward for the declared trainable scope.
   - Compare gradients against PyTorch references.
   - Hash frozen base weights before and after.

5. **Optimizer Update**
   - Run one selective update on phone.
   - Validate loss delta, trainable tensor mutation, and frozen tensor stability.
   - Block if any frozen base tensor mutates.

6. **Phone-Native Data Pipeline**
   - Stream raw text from Hugging Face directly on phone.
   - Tokenize on Oryon CPU using the Gemma tokenizer.
   - Pack sequences on phone.
   - Cache packed shards on UFS.
   - Keep Mac and RunPod out of the runtime data path.

7. **Integrated Training Loop**
   - Connect packed phone batches to the training runtime.
   - Produce a checkpoint or adapter artifact.
   - Emit audit logs, telemetry, hashes, and replay manifests.

8. **Sustained Authority Run**
   - Run long enough to expose memory leaks, thermal collapse, and checkpoint drift.
   - Capture battery, thermal, memory, KGSL/OpenCL telemetry, and error counters.
   - Performance is interpreted only after correctness gates remain green.

9. **Falsifier Review**
   - Independent falsifier agents attack:
     - random-init or wrong-weight substitution;
     - CPU fallback masquerading as OpenCL/Adreno;
     - pad-token metric inflation;
     - checkpoint mutation outside trainable scope;
     - host-side hidden data path;
     - tolerance relaxation;
     - regression against the passed layer gate;
     - narrative pass without artifact pass.

## GPD Integration

The final PRD should require a real `.gpd/` project, not only the fallback
YAML/runlog state, unless the GPD runtime itself is blocked.

Recommended GPD setup after PRD approval:

- initialize a formal project from the final PRD;
- create phases matching the gate ladder;
- use GPD plan/execute/verify for each phase;
- use verification protocols for:
  - numerical parity;
  - tolerance accounting;
  - memory-bound reasoning;
  - convergence/regression checks;
  - error propagation from FP32/BF16 conversion;
  - invariant preservation for frozen/trainable tensors.

GPD is useful only if it increases authority pressure. It must not become
document theater.

## GitHub Route

The old `main` route is deprecated for this lane. The PRD should direct the
executor to create the pivot branch as the canonical route, import Gemma4 Kernel
under the Polymath namespace, preserve evidence and artifact policy, and push
that branch to `https://github.com/Zer0pa/Polymath-AI`.

The import must exclude:

- model weights;
- raw phone output binaries;
- SDK files;
- build products;
- caches;
- phone token files;
- RunPod/private credentials.

## Open PRD Design Decisions

These should be decided in the final PRD, not left to overnight executor taste:

- trainable scope for the first phone update;
- E4B vs smaller Gemma variant for the first training loop if memory forces a staged route;
- exact HF corpus source for the first streamed phone training run;
- checkpoint artifact class and private storage policy;
- minimum sustained run duration after a valid update;
- whether Vulkan parity is required before backward, or only before backend comparison;
- whether QNN/HTP enters as frozen-forward later or remains parked.

## Readiness For Greenlight

After greenlight, write:

1. an extensive PRD replacing this prep note as authority;
2. an overnight executor handoff with no-interim-reporting doctrine;
3. a GPD initialization contract or fallback if the runtime blocks;
4. a GitHub branch/import plan that makes this pivot the main route.
