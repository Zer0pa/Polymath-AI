# Polymath-AI

> Product-page mirror for `/ai/Polymath-AI/`.
> Live public repo: [Zer0pa/Polymath-AI](https://github.com/Zer0pa/Polymath-AI).
> GitHub Markdown cannot reproduce the website typography, CSS, JavaScript, scroll behavior, or live bento layout; this README translates the product page into GitHub-safe Markdown evidence blocks.

## Product Page Mirror

**Product-page title:** Polymath-AI · Phone-side LLM training research lane · Zer0pa

**Product-page description:** Polymath-AI · public on-device LLM training research lane · ELO host smoke on Qwen2.5 · public PyPI 0.1.0 stale · QNN/LiteRT measured unsupported · phone-side training, sustained telemetry, and licensed-corpus execution remain open

### Hero Translation

> 00 · POLYMATH-AI · MOBILE LLM TRAININGLIVE LANE · 081431Z A research lane for phone-side LLM training. On-device language-model training research lane · Polymath-AI · PyPI 0.1.0 · Snapdragon 8 Elite target Polymath-AI is a training harness aimed at the Snapdragon 8 Elite (SM8750) phone chip. It trains only the first and last layers of a language model while the middle stays sealed and SHA-checked. The host smoke runs cleanly on Qwen 2.5 1.5B with the frozen middle showing zero weight changes. Phone compilation, licensed multilingual corpora, sustained device telemetry, and a public checkpoint are all open. This is a route, not a product.

## Positioning

| Field | Value |
| --- | --- |
| Section | ai |
| Product route | /ai/Polymath-AI/ |
| Live public repository | https://github.com/Zer0pa/Polymath-AI |
| Repo identity used here | Polymath-AI |
| Website display identity | Polymath-AI |
| Verdict | STAGED |
| Posture | evidence-infrastructure-first |
| Headline metric | 115/115 host tests pass; ELO frozen-hash invariant holds on Qwen2.5-1.5B; 19 falsifier gates specified. |
| Honest blocker | Phone attach, QNN/LiteRT compile truth, sustained device telemetry, and licensed corpus execution remain gates. Not yet a production model, public checkpoint, or completed training run. |
| Mechanics asset from product page |  |

## Key Metrics

| Metric | Value | Baseline |
| --- | --- | --- |
| HOST_TEST_SURFACE | 115/115 | docs/EXECUTION-REPORT.md overnight host run |
| ELO_QWEN_SMOKE | frozen-hash holds | Stage 1 smoke on Qwen2.5-1.5B |
| FALSIFIER_REGISTRY | 19 gates | docs/FALSIFIERS.md |
| DEVICE_GATE | BLOCKED | docs/PHONE-ATTACH-RUNBOOK.md; docs/DECISIONS.md |

## Proof Anchors

| Path | State |
| --- | --- |
| PRD.md | VERIFIED |
| RESISTANCE.md | VERIFIED |
| docs/DECISIONS.md | VERIFIED |
| docs/AUDIT-SPEC.md | VERIFIED |
| docs/EXECUTION-REPORT.md | VERIFIED |
| docs/FALSIFIERS.md | VERIFIED |

## What We Prove

- The PRD defines an on-device LLM training workstream with explicit boundary, device, corpus, audit, and falsifier gates.
- The overnight execution report records a host scaffold that can be cloned, installed, tested, and resumed by a fresh executor.
- ELO Stage 1 correctness was smoke-tested on real Qwen2.5-1.5B with frozen-hash invariants holding under the reported run.
- The falsifier registry specifies blocking gates for boundary, device, QNN, checkpoint, fertility, thermal, throughput, energy, license, and overclaim failures.
- Corpus policy separates allowed, decision-required, ambiguous, and prohibited license classes before training.

## What We Do Not Claim

- No production model or public checkpoint is released from this README.
- No clinical, human-subject, surveillance, biometric, identity-inference, or regulatory claim is made.
- No copyrighted or ambiguous corpus is approved for training without explicit license decomposition.
- No QNN/LiteRT acceleration claim is made until compile logs and delegate reports exist.
- No phone-side training result is claimed before REDMAGIC attach, telemetry, and falsifier gates pass.

## Blockers / Failures

> Phone attach, QNN/LiteRT compile truth, sustained device telemetry, and licensed corpus execution remain gates. Not yet a production model, public checkpoint, or completed training run.

## Verification Surface

| Code | Check | Verdict |
| --- | --- | --- |
| V_01 | Host scaffold and test surface reported in docs/EXECUTION-REPORT.md | PASS |
| V_02 | Boundary and audit specifications present | PASS |
| V_03 | Falsifier registry specified | PASS |
| V_04 | Phone attach and SoC probe | STAGED |
| V_05 | QNN/LiteRT compile truth table | STAGED |
| V_06 | Licensed corpus execution | STAGED |

## License

| Field | Value |
| --- | --- |
| License | LicenseRef-Zer0pa-OWNER_DEFERRED |
| Authority source | README.md |

## Upcoming Workstreams

| Category | Summary |
| --- | --- |
| Operations / External Dependency | REDMAGIC 10 Pro+ physical attach and SoC probe. QNN/LiteRT compile-truth table and delegate reports required before any phone-side training result is claimed. |
| Active Engineering | Licensed corpus decomposition and manifest completion. Corpus policy separates allowed, decision-required, ambiguous, and prohibited license classes before training can proceed. |
| Active Engineering | ELO Stage 2 device execution after phone attach gate passes. Frozen-hash invariant verified on host; device-side thermal, throughput, and energy falsifier gates pending. |
| Research-Deferred — Investigation Underway | KG projection and pending-upload manifest integration. Audit surface uses hash-chained rows and falsifier registry; KG node taxonomy shapes cross-workstream alignment. |

## Related Repos

No related repos are declared on the product page frontmatter.

<details>
<summary>Full Visible Product-Page Bento Translation</summary>

This section preserves the product page cells as Markdown text blocks. It intentionally omits shared site navigation, footer chrome, CSS, and scripts.

### Bento Cell 1

> 00 · POLYMATH-AI · MOBILE LLM TRAININGLIVE LANE · 081431Z A research lane for phone-side LLM training. On-device language-model training research lane · Polymath-AI · PyPI 0.1.0 · Snapdragon 8 Elite target Polymath-AI is a training harness aimed at the Snapdragon 8 Elite (SM8750) phone chip. It trains only the first and last layers of a language model while the middle stays sealed and SHA-checked. The host smoke runs cleanly on Qwen 2.5 1.5B with the frozen middle showing zero weight changes. Phone compilation, licensed multilingual corpora, sustained device telemetry, and a public checkpoint are all open. This is a route, not a product.

### Bento Cell 2

> 01 · THE GAPPHONE RUN MISSING “Training a language model on a phone still has no measured path from corpus to battery.”

### Bento Cell 3

> 02 · MARKETSUSER FIT Research infra teamsbest fit Mobile runtime teamsadjacent Corpus & license opsopen Production edge AInot now Consumer appsnot now Best fit is the research-infrastructure and mobile-runtime audience deciding what to staff; no model-revenue claim is made.

### Bento Cell 4

> 03 · VALUE OPENNOW Public repo and PyPI exist; the value is the training harness and its constraints, not a phone-trained model.

### Bento Cell 5

> 04 · INSIGHT A training harness, not a finished model.

### Bento Cell 6

> 05.0 · CURRENT TECHHOST, CPU, NATIVE Mobile language-model work usually means inference on the chip, with training kept in the cloud. The conventional route ships a trained model down to the device and never lets it learn there.

### Bento Cell 7

> 05.1 · OUR TECHSELECTIVE LAYER TRAINING Polymath trains only the boundary layers of a language model — layer 0, the final layer, and the language-model head — while every middle layer stays sealed and SHA-checked at frozen_changes = 0. Host smoke passes on Qwen 2.5 1.5B, with loss falling from 14.515 to 4.449 in five steps and the middle bit-identical across the run.

### Bento Cell 8

> 05.2 · BENCHMARKSHOST HARNESS Host testsPASSreported host Smoke baseQwen 2.51.5B params Checks19listed SoCSM8750SD 8 Elite resolved Host harnesspass Frozen middle0 changes Phone compileunsupported Device status: five SM8750 phone-compile rows currently measured unsupported; host harness passes.

### Bento Cell 9

> 06 · MEASUREMENTHOST ELO SMOKE Host smoke passes, phone compile remains unsupported.

### Bento Cell 10

> 06.1 · COMPARATIVE PERFORMANCE · HOST VS DEVICE STATUS Host harnessreported pass QNN/LiteRT compileunsupported Device telemetryopen Licensed corpusopen Host smoke · Qwen 2.5 1.5B, 5 training steps, loss 14.515 to 4.449, frozen middle unchanged. Phone compile, licensed corpus ingestion, and sustained device telemetry are not yet measured.

### Bento Cell 11

> 07 · KEY METRICSPOLYMATH-AI HOST HARNESS · PYPI 0.1.0 STALE

### Bento Cell 12

> 07.1 · HOST TEST SURFACE PASS Host harness pass · reported on developer machine

### Bento Cell 13

> 07.2 · SMOKE BASE Qwen 2.5·1.5B Smoke base model · frozen_changes = 0

### Bento Cell 14

> 07.3 · CHECK ROWS 19 Listed status rows · documentation coverage

### Bento Cell 15

> 07.4 · TARGET SOC SD 8 Elite·open SM8750 resolved · phone compile blocked

### Bento Cell 16

> 07.5 · ON-DEVICE THROUGHPUT null Metric absent · device path unsupported

### Bento Cell 17

> 08 · DETERMINISMFROZEN MIDDLE · SHA-CHECKED Frozen middle stays bit-stable while boundary layers train.

### Bento Cell 18

> 08.1 · WHAT DETERMINISTIC MEANSFROZEN_CHANGES = 0 Only the named boundary layers receive gradient updates — layer 0, the final layer, and the language-model head. The middle layers' weights are SHA-checked before and after every training pass; if any frozen weight moves, the run halts immediately and reports the offending tensor. The unit of bit-exactness is per-pass, host-side. Five steps on Qwen 2.5 1.5B leave the frozen middle unchanged across the entire run. No on-device determinism claim is made yet; the Qualcomm Neural Network and LiteRT paths are not exercised.

### Bento Cell 19

> 08.2 · THE FIDELITY GAP Honest Blocker · QNN/LiteRT compile on the Snapdragon 8 Elite is measured unsupported, so the scheduler cannot reach the device yet. On-device execution, sustained telemetry, licensed-corpus ingestion, and the next PyPI release all remain open. Tokenization currently bloats Zulu 2.68× and Greek 4.38× past target. No phone-trained model or public checkpoint exists.

### Bento Cell 20

> 09 FIVE PATHS FROM ONE PHONE-SIDE TRAINING LOOP.

### Bento Cell 21

> 09.1 · THIS REPO'S AMBITION The hinge is selective continual pretraining under real mobile constraints. Polymath-AI does not promise a finished model. It builds the scheduler, corpus discipline, and frozen-middle guarantee needed to answer one question honestly — whether training a useful language model on a phone, under battery and thermal limits, is worth doing at all.

### Bento Cell 22

> 09.2 · WHAT WORKS NOW Working now: host training harness on Qwen 2.5 1.5B, frozen-middle SHA-check, scheduler framing, and a resolved chip target.

### Bento Cell 23

> 09.3 · WHAT'S STILL OPEN Still open: phone compile path, sustained device telemetry, licensed multilingual corpora, and a published checkpoint with release evidence.

### Bento Cell 24

> 09.4 · ADAPTATION · NEAR-TERM (12–24 MO) The fine-tune leaves the data centre A mobile-runtime engineer who can land a boundary-layer training pass on a flagship chip stops needing a remote fine-tune to personalise a model. Adaptation becomes a battery decision on the device, not a procurement decision with a cloud vendor.

### Bento Cell 25

> 09.5 · CORPUS CUSTODY · NEAR-TERM (12–24 MO) Multilingual data stops travelling When the training step runs on the handset, the multilingual text a model learns from no longer has to leave the phone. A speaker of an underrepresented language can contribute to their own model without their words crossing a corporate boundary.

### Bento Cell 26

> 09.6 · PERSONAL MODELS · MID-TERM (24–48 MO) One model, one person, one phone If selective training holds at scale, a model can drift toward the person carrying it rather than the average of millions of strangers. The phone becomes a place where a small, personal model improves over months instead of being replaced quarterly.

### Bento Cell 27

> 09.7 · RECEIPTS · MID-TERM (24–48 MO) Mobile training answers to evidence A regulator or platform reviewer who asks how an on-device model changed can be answered with a record — layer touched, update size, battery cost, quality movement — rather than a marketing claim. Phone training becomes something assessable, not just demonstrated.

### Bento Cell 28

> 09.8 · LOCAL AGENCY · PARADIGM (48 MO+) The phone becomes a knowledge instrument Once training, telemetry, and corpus custody all fit inside the device, the phone stops being the last mile of someone else's model. It becomes a bounded place where a person's language, history, and tasks shape what their model knows.

</details>

---

Source mapping: product route `/ai/Polymath-AI/` -> live public repo `Zer0pa/Polymath-AI`. README generated from product-page authority plus retained install/dev commands only.
