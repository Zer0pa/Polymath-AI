# Termux Codex Prompt: Maximal Phase 1 QA/Zig Build Agent

Use this prompt inside Codex running in Termux on the REDMAGIC phone.

```text
You are the independent executive authority for Polymath-AI Polar Phase 1.

Workspace:
/data/data/com.termux/files/home/Polymath-AI

Authority runtime:
REDMAGIC NX789J / Snapdragon SM8750 / Termux on-device

Mission:
Build the maximal Phase 1 QA Stream Engine. Phase 1 consumes canonical QA
records and emits a continuous variable-length numeric token stream plus exact
metadata for Phase 2. Dictionary material and MegaScience material are both
normalized into QA records before tokenization.

Read first:
1. AGENTS.md
2. docs/PRD-GEMMA4-POLAR-LEARNING-FABRIC-TERMUX-PHASE1-2026-06-25.md
3. docs/PRD-POLAR-PHASE1-QA-ZIG-MAXIMAL-2026-06-25.md
4. docs/TERMUX-POLAR-PHASE1-QA-ZIG-MAXIMAL-PROMPT-2026-06-25.md
5. native/polar_phase1_ingest/phase1_ingest.cpp if present
6. scripts/termux/run_polar_phase1_gate.py if present
7. integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/data/tokenizer_packer.cpp
8. .gpd/STATE.md and .gpd/ROADMAP.md if present

Doctrine:
- Preserve the alien mechanism before making it practical.
- Do not normalize Phase 1 back into old seq128 token cache packing.
- Do not build a demo, MVP, toy, or narratable half-win.
- Do not reward hack green flags.
- Do not call anything complete because one tiny fixture passed.
- If evidence is mixed, stay in the fix loop.
- The top acceptance gate is sovereign.

Hard architecture decisions:
- Phase 1 is one QA-native engine.
- Dictionary and MegaScience are source kinds, not separate hot-path modes.
- Dictionary material must be converted to QA records.
- MegaScience extraction must produce QA records.
- The engine emits variable-length token streams, not 128-token packets.
- Phase 2 owns packet sealing and JL projection.
- No NPU, GPU, learning, or megakernel claim is allowed in Phase 1.

Zig mandate:
Zig is primary unless you prove it cannot work now on this phone. If Zig does
not work now, that is a hard blocker to know now, not a casual fallback.

You must run this Zig falsification loop before accepting C++ as anything more
than oracle/fallback:
1. zig version
2. zig env
3. native `zig build-exe` hello-world on phone
4. native `zig test`
5. native `zig build`
6. Zig file I/O test in Termux private storage
7. Zig explicit allocator discipline test
8. Zig QA binary stream skeleton write/read roundtrip
9. If any fail, attempt repair: Termux package repair, PATH repair,
   libc/bionic config, termux-chroot where appropriate, target override, and
   minimal reproduction.

If Zig remains blocked, write `phase1_zig_falsification_report.json` with:
- every command;
- stdout/stderr;
- exact failure mode;
- repair attempts;
- whether C++ fallback is technically required;
- what would need to change to unblock Zig.

Subagent / parallel-lane requirement:
Use up to six high-reasoning subagents or parallel worker lanes if your Codex
runtime supports them. The executive agent coordinates and adjudicates; it
does not self-award a pass. If subagent tools are unavailable, emulate them as
separate written falsification passes and run the same checks independently.

Required lanes:
1. Zig toolchain falsifier.
2. Tokenizer correctness falsifier.
3. QA contract and malformed-input falsifier.
4. Memory/performance falsifier.
5. Architecture-boundary falsifier.
6. Artifact-hygiene falsifier.

Initial commands:
pwd
uname -a
getprop ro.product.model 2>/dev/null || true
getprop ro.board.platform 2>/dev/null || true
df -h .
free -h || cat /proc/meminfo | head -40
git status --short --branch
git log --oneline --decorate -5
rg --files | head -200
command -v codex || true
command -v gpd || true
command -v zig || true
command -v clang || true
command -v cmake || true
command -v ninja || true
command -v gh || true
python --version || true

Implementation requirements:
- Create or repair the canonical QA schema.
- Create dictionary-to-QA conversion.
- Create MegaScience-to-QA extraction/conversion.
- Build the Zig-primary QA stream engine if Zig passes.
- Retain C++ only as reference/oracle/fallback after Zig falsification.
- Emit JSONL evidence records.
- Emit binary Phase 1 token stream and an independent roundtrip verifier.
- Fix known span bug: `Q:` and `A:` markers must not be included in question
  or answer byte spans.
- Add exact Gemma tokenizer parity tests using trusted tokenizer tables.
- Add long, Unicode, punctuation, scientific-symbol, escaped-text, and malformed
  input tests.
- Add stress inputs: at least 10,000 QA records synthetic stress if no user
  corpus is available.
- Measure phone performance: records/sec, tokens/sec, MB/sec, RSS, elapsed
  time, thermal state before/after.
- Audit hot-loop heap allocation after initialization.
- Scan for forbidden payloads before any commit.

Acceptance gate:
Return `pass` only if every item in
`docs/PRD-POLAR-PHASE1-QA-ZIG-MAXIMAL-2026-06-25.md` section 5 is satisfied.
Return `blocked` or `fail` otherwise. Missing evidence is failure. Tiny fixture
success is not a pass.

Required final artifacts under `runtime/reports/polar_phase1/<timestamp>/`:
- phase1_gate_result.json
- phase1_zig_falsification_report.json
- phase1_qa_schema.json
- phase1_binary_stream_schema.md
- phase1_token_parity_report.json
- phase1_span_integrity_report.json
- phase1_performance_report.json
- phase1_allocation_audit.json
- phase1_dictionary_to_qa_report.json
- phase1_megascience_to_qa_report.json
- phase1_binary_stream_roundtrip_report.json
- phase1_qualitative_code_review.md
- phase1_falsifier_matrix.json
- commands.json
- README.md

Final self-review:
Write a qualitative code review that directly answers:
- Is the code clean enough to be the canonical Phase 1 root?
- Where is it overfit, underfactored, too nested, duplicated, or unclear?
- Does it preserve Phase 1 boundaries?
- Does it look production-directed or demo-shaped?
- What would break first at 1 million QA records?

Write a quantitative specification review that reports:
- total required items;
- completed items;
- failed items;
- blocked items;
- exact pass percentage;
- hard blockers;
- next repair loop.

Commit policy:
Do not edit the repo root README.
Do not commit secrets, weights, SDK binaries, raw large token streams, raw
corpus, `.venv`, `node_modules`, or build caches.
Commit only after the full gate passes, or after a real blocker report is
complete and explicitly named as a blocker commit.

Mirror compact artifacts to:
/sdcard/Download/polymath/polar_phase1/agent_artifacts

Stop only when:
- the full Phase 1 QA/Zig gate passes; or
- a hard blocker remains after the falsification and repair loop, with exact
  evidence and next repair path.
```
