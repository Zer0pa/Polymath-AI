# Wave-2: What Learning Loop Does The SoC Physically Want?

**Date:** 2026-05-16
**Role:** Wave-2 research agent (upstream reframe)
**Substrate:** RedMagic 10 Pro Plus, Snapdragon 8 Elite SM8750, 24 GB LPDDR5X (~85 GB/s), Adreno 830, Hexagon NPU, UFS 4.1, active cooling + bypass charging, hours-to-days operational envelope.
**Discipline:** Resistance V2. The operator explicitly wants the maximal interpretation: this wave does **not** anchor on CPT-shaped backprop. It re-asks whether that anchoring is itself the architectural error.
**Status:** Surface-of-candidates document. Does **not** pick a loop. Does **not** produce Tier-1/2/3. Does **not** translate to a model or method. The next agent (synthesis) gets to read this without a pre-baked recommendation.

---

## 0. The reframing in one paragraph

Wave-1 ranked everything by "does it scale to LLM-class continued pretraining of a backprop-shaped objective on a fixed corpus." Under that frame, only three families survived: bubble-aware pipeline-parallel BP, MeBP + MobiZO/MeZO (FO + ZO mix), and ZeroQAT-class quantization-aware on-device training. That ranking is *correct under its frame*. But the frame imports an assumption from cloud LLM practice that the SoC's design intent does not support: that "training" means "iterating an SGD-style update over a fixed, replay-shuffled corpus until held-out loss stops dropping." The SoC was not built for that. The SoC was built for **gaming + real-time inference + sustained mobile compute with mutable state in fast cache, persistent writes infrequent, hours of sustained operation under active cooling**. That physical signature is a strong design signal. Read literally, it favors a *streaming* loop with *bounded* memory, *cheap* forward, *expensive* persistent writes, *long-running* operation, and *external sensory input* (because the device sits next to a human in the world). Wave-1 surfaced none of that as architectural input — it only used the SoC's properties to score how well CPT-backprop fits. This wave swaps the dependency: the substrate is given, the loop family is the variable.

The honest result of doing that is *not* "we discovered the secret right loop." It is that **at least five candidate loop families show a closer hardware-design match than CPT-shaped backprop does**, and one of them (continual prediction with selective consolidation) maps to the SoC's read/write asymmetry almost exactly. None of these has LLM-scale receipts. But the question wave-2 was asked is not "what has receipts," it is "what does the hardware want." Those answers diverge, and the divergence is the architectural finding.

---

## 1. The hardware-design-signal argument

The SoC is not a small datacenter card. Six physical facts together imply a non-CPT loop class:

| Physical fact (from prior wave-1 docs) | What it physically means | What loop class this favors |
|---|---|---|
| Hexagon NPU is forward-strong, backward-hostile; 12 TFLOPS FP16 forward HMX vs no published backward kernel anywhere | The bulk compute on this chip is *cheap repeated forward inference*. Backward is structurally a sidecar, not a sibling. | Loops that turn most of compute into forward prediction and confine weight updates to a small, controlled surface. |
| 8 MiB software-managed TCM + 1 MiB L2 on Hexagon; 24 GB unified LPDDR5X DRAM at 85 GB/s; UFS 4.x at ~4 GB/s | Three tiers of memory with sharp speed cliffs. Fast-tier mutable state is small; large-tier persistent writes are *orders of magnitude* slower than reads. | Loops with *small mutable working state* and *infrequent batched persistent writes* — e.g. fast-weight inner loops with periodic consolidation, not per-token DRAM-thrashing gradient updates. |
| Active fan + bypass charging + fridge mode in operator's regime → hours-to-days sustained operation | The device is built to *run continuously*. The relevant time-scale is hours, not the seconds-to-minutes of a phone task. | Loops that *exploit continuous operation*: streaming prediction, slow consolidation, sleep/wake phases. Loops that need a one-shot result do not use this signature. |
| Adreno 830 is a graphics-priority TBDR GPU with strong sustained FP32/FP16 throughput, COMPUTE-only queue is the natural training surface | The device's flagship use case is *real-time stream processing under sustained load* — that is what a game is, at the GPU level. | Loops shaped like real-time stream processing: a forward loop running at "game-tick" rate, with selective updates triggered from inside that loop rather than queued from an outer training driver. |
| Snapdragon 8 Elite Oryon CPU has rich control surface (2 perf + 6 efficiency cores, NEON/SVE2, mature OS, persistent storage I/O) | The CPU is a *long-running supervisor*, not a thin glue layer. It can host a scheduler, a replay buffer, an episodic memory, and an optimizer running on its own clock. | Loops with a non-trivial CPU-side control / consolidation phase separate from the accelerator-side forward stream. |
| Sensors: microphone, camera, IMU, touch, network, time. The SoC is *embedded in a stream of natural data*. | The device has free, perpetual access to a real, embodied data stream. A CPT corpus on this device is *artificial*; a sensory stream is *native*. | Loops that consume a streaming non-stationary input as their primary signal: continual prediction, world-models of the user's environment, online RL/TD over a real reward stream. |

If you collapse these six facts into one sentence, the SoC says: *"I am a continuously running predictor over a streaming sensory/task input, with cheap forward repetition, small mutable scratch memory, expensive persistent writes, and a long supervisor process."*

CPT-shaped backprop on a fixed corpus does not match any of those properties cleanly. It matches one: "the accelerator can do forward fast." But it inverts every other property: it wants persistent writes *per step* (every gradient update mutates a large weight tensor), it wants the corpus to be *fixed and shuffled* (not streaming and non-stationary), it wants weight updates to be the *main event* (not an exception triggered by surprise), and it has no use for the embedded sensory stream the SoC sits inside. The wave-1 result that CPT-style methods need ELO + ping-pong + dual-residency + replay buffer shipped from UFS is exactly the symptom of pushing a *non-streaming* loop onto streaming hardware.

This is the architectural finding the wave-1 frame could not see: **the SoC's design intent reads as continual / streaming / sleep-replay-style learning hardware, with CPT-shaped backprop as a possible but unnatural workload class to host on it.**

Note carefully: this finding does *not* automatically promote any single candidate loop to "the answer." It only says wave-1's ranking is unfair to streaming-loop candidates because the rubric had "LLM-CPT scale receipts" as the dominant axis. If we are allowed to take "hardware-loop fit" as a comparably weighted axis, the ranking is unrecognizable. The rest of this document analyzes the candidates without resolving that tension, because resolving it requires picking an authority metric and that is a synthesis decision, not a survey decision.

---

## 2. Per-candidate analysis

Template per candidate:
- **Loop structure**
- **Why the SoC's physical structure favors this loop**
- **Largest demonstrated scale** (honest about what exists and what doesn't)
- **Corpus/data assumption**
- **Training signal**
- **Consolidation / persistence model**
- **Hardware-fit risks**
- **Relationship to Polymath's stated ambition**
- **Falsifiers**
- **Key sources**

### 2.1 Continual prediction with selective consolidation (hippocampus / cortex shape)

- **Loop structure.** A model continuously predicts the next observation (token, frame, sensor read, action consequence) in a stream. Each prediction produces an error signal. Most predictions are absorbed without any weight change: only high-surprise or high-value events trigger consolidation. Consolidation may be (a) an immediate small fast-weight write, (b) an entry to a replay buffer, or (c) deferred to a periodic / sleep phase. Two systems run concurrently: a fast, plastic, episodic encoder (hippocampus-analog) and a slow, stable, structural network (cortex-analog). The fast system learns instantly from single examples; the slow system absorbs patterns from replay over many cycles. This is the **Complementary Learning Systems** framework, formalized in neuroscience by McClelland, McNaughton & O'Reilly (1995) and recently extended in ANNs by HiCL (arXiv:2508.16651, 2025), brain-inspired replay (van de Ven et al., *Nature Communications* 2020, https://www.nature.com/articles/s41467-020-17866-2), sleep-like unsupervised replay (Tadros et al., *Nature Communications* 2022, https://www.nature.com/articles/s41467-022-34938-7), semi-parametric memory consolidation (arXiv:2504.14727), and SCM: Sleep-Consolidated Memory with Algorithmic Forgetting for LLMs (arXiv:2604.20943).
- **Why the SoC's physical structure favors this loop.** Almost a 1-to-1 match:
  - "Most predictions absorbed without weight change" → fast forward on Hexagon NPU, *no* DRAM write per token. This is the SoC's strongest mode.
  - "High-surprise event triggers consolidation" → infrequent persistent write to UFS / mutable cortex weights. Matches UFS's slow-write-but-sustained-bandwidth profile.
  - Fast/slow split → fast plastic surface on Adreno+CPU (small, mutable, in DRAM); slow stable trunk on Hexagon (compiled, frozen, on UFS-backed quantized weights). Mirrors the SoC's read/write tier asymmetry directly.
  - Sleep replay → uses the device's natural overnight idle window for consolidation work, which the operator explicitly named ("phone thinks overnight").
  - Episodic store → CPU + UFS, exactly the substrates already built for persistent retrieval.
  - The continual forward stream → the sensor stream / interaction stream the device already sits inside.
- **Largest demonstrated scale.** Small. Brain-inspired replay (van de Ven 2020) demonstrated on CIFAR-100 and split MNIST class-incremental learning. SleepNet / sleep-like replay (Tadros 2022) demonstrated on incremental MLP/CNN training, MNIST/CIFAR class incremental. HiCL (2025) tested on continual-learning benchmarks of CV class-incremental scale, no LM. SCM (arXiv:2604.20943, 2026) is the first attempt to put sleep-consolidated memory on top of an LLM, but it is a memory/inference scaffold, not an LLM trained end-to-end by the loop. **No 1B+ language model trained from scratch under this loop family exists.**
- **Corpus/data assumption.** Streaming, non-stationary. Sequence is what is actually presented to the agent; *not* shuffled. Replay buffer is *internal* — a learned compression of past experience, not the raw corpus. Crucially: this loop does not require a fixed Polymath corpus at all. It requires *a continuous prediction target*.
- **Training signal.** Prediction error (or surprise: -log p(observation | model)). The error is *gated* by a separate mechanism — typically a learned or hand-set surprise threshold, or an explicit value signal — into "absorb" vs "consolidate."
- **Consolidation / persistence model.** Two-phase. Wake: fast write to small plastic surface + entry into replay buffer for high-surprise events. Sleep / idle: replay of recent episodes interleaved with old ones, with slow weight updates to the stable trunk (typically local Hebbian, contrastive, or distillation losses; *not* per-step global gradient). This is the natural "infrequent persistent write" that matches the SoC's storage signature exactly.
- **Hardware-fit risks.**
  - The "stable trunk" is still a large parametric network that has to learn from replayed episodes. If that consolidation step uses backprop, the wave-1 cost analysis returns: trunk update is still expensive. The loop only saves cost if the trunk update is *infrequent* (overnight) or *local* (Hebbian / contrastive at layer scope, not global BP).
  - Replay buffer storage on UFS is cheap; replay buffer retrieval at training time is fine because UFS sequential read >> training token rate. But the *selection* of what to replay is an open algorithmic question (importance sampling? episodic similarity? curriculum?).
  - Fast plastic surface size: if the "hippocampus" is too small, capacity for new episodes is exhausted in hours; if too large, it competes with the trunk for DRAM. Sensitivity not characterized at LM scale.
- **Relationship to Polymath's stated ambition.** This loop produces a *different kind* of model than CPT. The stable trunk is still a large parametric model that *encodes the distribution of the input stream*, so if the input stream contains the Polymath corpus, the trunk eventually encodes Polymath content. But the trunk is not "the result"; the model is the *trunk + plastic surface + episodic store + scheduler* together. As an artifact it is closer to a personal-cognitive-system than to "an LLM checkpoint." This is a real reframing of what Polymath *is* — see section 4.
- **Falsifiers.**
  - F1: Stable-trunk consolidation step is itself expensive enough that "overnight" doesn't fit in overnight: e.g. consolidating one day's worth of replay events takes >12 h on this SoC. Would force the trunk smaller (and the model less ambitious) or the consolidation cadence longer than daily.
  - F2: Without a sensory / interaction stream, the input degenerates into "a CPT corpus presented in order," which collapses the loop into a slow / awkward CPT variant. If the deployment scenario does not produce a real stream, the loop is wrong-for-substrate.
  - F3: Selective-update gate fires too rarely (model is rarely surprised) → no learning happens. Or too often (model is always surprised) → loop collapses to per-token update = CPT in disguise. Gate-tuning becomes the central algorithmic problem.
  - F4: No published "continual prediction with selective consolidation" model has reached LM-class generative perplexity. If by mid-2027 no such result exists at >=125M params trained end-to-end under this loop, the scaling assumption fails.
- **Key sources.** McClelland, McNaughton, O'Reilly 1995 (CLS original). Kumaran, Hassabis, McClelland 2016 *Trends Cog Sci* (CLS revisited). van de Ven et al. *Nature Communications* 2020 (brain-inspired replay). Tadros et al. *Nature Communications* 2022 (sleep replay). HiCL arXiv:2508.16651 (2025). Semi-parametric memory consolidation arXiv:2504.14727 (2025). SCM arXiv:2604.20943 (2026). Recurrent network model of planning explaining hippocampal replay, *Nature Neuroscience* 2024.

### 2.2 Online value-function / TD learning (continual predictive policy)

- **Loop structure.** Agent has a value function V(s) or Q(s, a). Each interaction step produces a reward (real or intrinsic). TD error δ = r + γV(s') - V(s). Updates to V are bounded-memory and per-step. Policy is derived from V (greedy, softmax, or via actor-critic with policy gradients). The whole loop runs *continuously* on a stream of (s, a, r, s') — no replay buffer required in pure online TD, though experience replay is the de facto standard.
- **Why the SoC's physical structure favors this loop.** TD updates are tiny — a per-parameter scalar arithmetic operation gated by a small δ signal. Bounded memory: no full corpus storage. Long-running operation: matches the SoC's hours-to-days envelope. The forward inference (V or π) runs on Adreno/Hexagon; the TD update runs on CPU. Critically: the device is *embodied* — it has a real user interaction stream, so the reward signal can be real-world (task success, dwell time, explicit user feedback) rather than synthesized. Recent work (Process Reward Models for LLM Agents, arXiv:2502.10325; AgentRM, ACL 2025) explicitly treats LLM-as-agent as a Q-function-shaped training target.
- **Largest demonstrated scale.** RL-trained LLMs at scale exist (RLHF and successors; recent agentic RL work like Meta-RL Induces Exploration in Language Agents, arXiv:2512.16848). But these are *cloud-trained* policies that are then deployed read-only. **No 1B+ LLM has been trained end-to-end via online TD on-device.** The closest is Discovering state-of-the-art RL algorithms (*Nature* 2025 / s41586-025-09761-x), which meta-learned an RL rule — proves that the rule discovery is itself a non-trivial open problem.
- **Corpus/data assumption.** Streaming user/task interaction. The "corpus" is the trajectory of the agent in the environment, which may include the user's task stream, the device's sensor stream, or a simulator's output stream. No fixed dataset.
- **Training signal.** Reward — sparse, delayed, possibly hand-shaped or LLM-shaped. TD error is the per-step credit signal.
- **Consolidation / persistence model.** Continuous, small-write per step on the trainable policy/value parameters. If using experience replay, episodic buffer is on UFS, replay batches at slow cadence. Persistent writes are *small* (only the trainable subset of the policy net) and *frequent* (every step), so this loop pushes the *write rate* axis harder than continual prediction does. Memory hierarchy fit is therefore weaker than continual prediction.
- **Hardware-fit risks.**
  - **Sample efficiency catastrophe.** RL is notoriously sample-hungry. Even on-policy actor-critic on LM-scale policies needs ~10⁶–10⁹ interaction steps to converge on non-trivial tasks. A single user interacting with a phone produces O(10²–10³) interactions/day. The wall-clock-to-target-quality may be years, not hours.
  - **Reward sparsity.** Without dense reward shaping, the agent gets few learning signals. Hand-shaping rewards is brittle; LLM-shaping (PRMs) requires running the PRM at training time → more on-device compute.
  - **Exploration on a user's phone is dangerous.** Random action selection in a real user environment is a UX failure mode and a safety risk. Restricting exploration kills sample efficiency.
- **Relationship to Polymath's stated ambition.** Inverts it. Under this loop, "Polymath" is a *policy*, not a corpus-compressed LM. The artifact is "an agent that has learned to act well in the user's environment over hours/days/weeks." The training corpus is the user's life, not a static text dump. **This is the most aggressive reframing in this document.** It implies the operator's "training, not personalization" distinction needs sharpening — under TD learning, the policy is trained from scratch (or near-scratch) on the user's interaction stream, which is both "training" and "personalization" simultaneously.
- **Falsifiers.**
  - F1: Sample budget. With realistic on-device interaction rates, can the loop reach competence at any task within months of operation? If no measured RL agent has converged on a comparable task at comparable sample budget, this loop is too slow for the device.
  - F2: Reward source. Without a credible source of dense or shaped reward, the loop is reward-starved.
  - F3: Exploration policy. Without safe exploration, on-user-device training is a UX failure.
  - F4: Policy quality ceiling. Even with perfect optimization, can an RL-trained policy from a phone-scale interaction stream exceed the quality of a pretrained LM that already encodes general world knowledge? Probably not, unless bootstrapped from a pretrained base — at which point this loop is *fine-tuning* a pretrained model, not "training" it.
- **Key sources.** Sutton & Barto, *Reinforcement Learning: An Introduction* 2018. Discovering state-of-the-art RL algorithms, *Nature* 2025 (https://www.nature.com/articles/s41586-025-09761-x). Process Reward Models for LLM Agents, arXiv:2502.10325. Meta-RL Induces Exploration in Language Agents, arXiv:2512.16848. Review of RL for LLMs, http://www.liziniu.org/docs/RL4LLM_Survey.pdf.

### 2.3 World-model loops (Dreamer-shape)

- **Loop structure.** Train a *forward model* of some environment: given the current observation and an action, predict the next observation (or its latent embedding). Once the world model is good enough, the agent acts by *imagined* rollouts in the latent space — no environment query at decision time. Weight updates to the world model are driven by *prediction error in the environment*. The policy is trained inside the world model's imagination. JEPA (LeCun) and Dreamer (Hafner) are the two main families.
  - I-JEPA / V-JEPA (Meta, 2023–2025): predict masked latent regions instead of pixels. V-JEPA 2 (June 2025) scales to ~1M hours of internet video.
  - Dreamer / DreamerV3 / Dreamer 4 (Hafner et al.). Dreamer 4 (Sept 2025, arXiv:2509.24527) is the first agent to obtain Minecraft diamonds purely from offline video-action data; inference at ~20 FPS on a single H100. The shortcut-forcing trick enables 4-step rollouts matching 64-step diffusion quality.
- **Why the SoC's physical structure favors this loop.** Two strong matches and one weakness.
  - Match 1: The world-model's *forward* (which is most of inference and most of the imagined-rollout compute) is exactly what Hexagon NPU is built for. Dreamer 4's "4-step shortcut rollout" pattern is a forward-heavy loop in the SoC's preferred shape.
  - Match 2: World-model loops have a natural *separation* between fast imagined-policy queries and slow world-model updates. The fast queries are real-time, the slow updates are batch. This separation maps directly to the SoC's wake/idle split.
  - Weakness: world-model *training* still requires backprop through a generative or contrastive objective. The compute cost of updating the world model from a stream is non-trivial. JEPA-style latent prediction may be cheaper than pixel-level Dreamer reconstruction.
- **Largest demonstrated scale.** Dreamer 4 (~2509.24527) is the strongest contemporary result, trained on offline video-action data; not LM scale, not phone-deployable. V-JEPA 2 trained on ~1M hours video; encoder is ViT-L scale, not LLM scale. JEPA family has not produced a generative LM. **No 1B+ LLM trained as a world model exists.** LeCun explicitly positions JEPA as a *replacement* for autoregressive token prediction at scale; this is a research bet, not a result.
- **Corpus/data assumption.** Streaming experience or large offline trajectory dataset of (state, action, next-state). Could be: simulator output, video corpus (V-JEPA), user-task interaction logs, robot trajectories. The Polymath text corpus is *not* a natural fit for this loop unless reframed as a stream of (context, user-action, next-context) tuples — which is an interesting reframing but not what wave-1 assumed.
- **Training signal.** Prediction error (reconstruction loss for Dreamer, embedding distance for JEPA). Optionally augmented with reward for policy learning.
- **Consolidation / persistence model.** The world model is updated periodically (batch updates), the policy is updated via imagined rollouts continuously. So weight writes are clustered (world model: low cadence, large updates) — fits the "infrequent persistent write" signature. The imagined rollout phase produces *no* persistent writes — pure forward. Strong fit.
- **Hardware-fit risks.**
  - Training the world model itself requires backprop through a sequence model. If the world model is transformer-sized, the world-model training step is as expensive as a CPT step — the loop doesn't save anything until you go to imagined-rollout-dominated learning.
  - Reward source for policy learning has the same problems as 2.2.
  - On-device world model needs an *environment*: simulator (heavy on-device compute), real-world sensors (latency-sensitive, requires sensor fusion), or text-based environment (where the world is "the conversation," and the loop collapses toward something between TD and continual prediction).
- **Relationship to Polymath's stated ambition.** Reframes Polymath as a *predictive simulator* of the user's task / language environment. The artifact is a world model that can imagine continuations — which is uncomfortably close to "a generative LM," but trained by a different objective. JEPA-style would produce a *non-generative latent predictor* — quite far from "an LLM you can sample from." This is a fork: pixel-Dreamer-style → still a generative model, just trained as a world model; JEPA-style → not a generative model at all, an embedding predictor.
- **Falsifiers.**
  - F1: No LLM-scale generative world model exists; if by 2027 no JEPA / Dreamer / equivalent has produced a generative LM at LLM perplexity, the scaling claim fails.
  - F2: The "imagined rollout" advantage requires the world model to be cheap enough at inference that 4–64 rollouts per real query are affordable. On phone, even 4 forwards through a 4B world model may be too expensive at user-facing latency.
  - F3: Without a real environment / stream, the loop collapses to "world model trained as a generative LM from text" = CPT in different clothing.
- **Key sources.** Hafner et al. *Dream to Control* 2019, *DreamerV3* 2023, *Dreamer 4* arXiv:2509.24527. I-JEPA (Assran et al. 2023), V-JEPA 2 (Meta 2025), V-JEPA 2.1 (Mar 2026). World-model survey: arXiv:2411.14499 (2024). Curiosity-driven exploration (Pathak et al. 2017, arXiv:1705.05363) → world-model prediction error as the intrinsic reward, recently revisited in *From Curiosity to Competence* arXiv:2507.08210 (2025).

### 2.4 Sleep-replay-style consolidation (wake/sleep explicit split)

- **Loop structure.** Explicit two-phase architecture. **Wake phase**: model runs in deployment mode — predicts, accumulates prediction errors, writes interesting episodes to a replay buffer. No weight updates, or only tiny fast-weight updates. **Sleep phase**: model goes offline, replays recent + selected old episodes, runs unsupervised consolidation (typically with Hebbian-style local rules or contrastive distillation), updates the stable weights. Cycle repeats.
- **Why the SoC's physical structure favors this loop.** The operator explicitly named this fit ("phone thinks overnight"). It is the cleanest match in this entire document:
  - Wake = inference only on Hexagon/Adreno during user-active hours → forward-strong, write-free, low thermal load (matches gaming/use pattern).
  - Sleep = batch compute during idle hours (e.g., 1 AM – 6 AM, charging, on a desk, no user attention) → can drive Adreno + CPU hard with fan + bypass charging without UX cost. The fridge regime *is* literally a sleep accelerator.
  - The "infrequent persistent write" property is sleep's write phase, batched.
  - Energy-budget axis: wake uses ~mobile-class power; sleep can use ~appliance-class power. The operator's setup (charging + fan + fridge) is *specifically* a sleep-friendly setup.
- **Largest demonstrated scale.** Sleep-replay-style in deep nets is small-scale to date: Tadros et al. 2022 (Nature Comms) on incremental MNIST/CIFAR; Sleep Replay Consolidation (SRC, AAAI 2025) on standard CIL benchmarks; NeuroDream (SSRN 2025) on continual CIFAR-class problems. **No LLM trained under this loop exists.** The closest LLM-scale attempt is SCM: Sleep-Consolidated Memory for LLMs (arXiv:2604.20943, 2026), but it's a memory layer over a pretrained LLM, not an LLM trained by the loop.
- **Corpus/data assumption.** Streaming during wake; episodic buffer replay during sleep. The episodic buffer is *internal*, not the original corpus — it's a learned compression of "what was worth remembering." So even if the Polymath corpus is the initial seed, after one wake/sleep cycle the loop operates on its own internal trace.
- **Training signal.** Wake: surprise / prediction error / value / explicit user feedback drives entry into the buffer. Sleep: local Hebbian or contrastive distillation drives the slow weight updates. Notably, the sleep update *is not gradient descent on a global loss over a corpus* — it is a local rule operating on replayed activations. This is what makes the loop "different" rather than "backprop on a smaller batch."
- **Consolidation / persistence model.** Two-phase explicit. Wake writes nothing or only fast-weight. Sleep writes the entire updated trunk to UFS at end of cycle. Perfect match to the SoC's write profile.
- **Hardware-fit risks.**
  - Quality of the sleep-phase local rule. Hebbian no-feedback (SoftHebb) tops out at 27.3% ImageNet top-1 (wave-1 numbers). If the sleep consolidation is too weak, the model's stable weights never get good. There is no published demonstration of sleep-phase consolidation reaching LM-quality.
  - Wake/sleep scheduling: when is the model "off" enough for a sleep phase? If the user uses the phone at night, sleep is short. The operator's setup (dedicated device, fridge regime) handles this — but a generalized phone-Polymath does not.
  - Episodic buffer size and selection policy. Unbounded buffer → UFS fills. Bounded buffer with wrong selection → forgetting.
- **Relationship to Polymath's stated ambition.** This loop produces a model that *evolves* between wake and sleep phases. The artifact is *checkpointable* at sleep-end, so it is still "a model you can extract." It is closer to the operator's stated ambition (a model trained on Polymath content) than 2.2 or 2.3 are. The Polymath corpus can seed the initial buffer; subsequent sensory streams (or further corpus presentations) shape what the model becomes. It is "training" in the operator's sense.
- **Falsifiers.**
  - F1: Sleep-phase local rule's quality ceiling. If sleep consolidation cannot reach BP-equivalent perplexity on a held-out test, the loop's stable weights are strictly worse than a CPT-trained model on the same compute.
  - F2: Wake-phase fast-weight surface is too small to matter, or too large to be cheap.
  - F3: Replay buffer selection algorithm. No principled answer at LM scale.
  - F4: No published wake/sleep-trained LM. If by 2027 none exists, the scaling claim fails.
- **Key sources.** McClelland, McNaughton, O'Reilly 1995. Tadros et al. *Nature Comms* 2022 (https://www.nature.com/articles/s41467-022-34938-7). Sleep Replay Consolidation (Tadros et al. AAAI 2025). NeuroDream SSRN 2025. PNAS 2022 hippocampus-neocortex sleep consolidation model. SCM arXiv:2604.20943 (2026). Brain-inspired replay van de Ven et al. *Nature Comms* 2020.

### 2.5 Test-time training with replay-gated promotion to durable adapters

- **Loop structure.** Per-session (per-conversation, per-task, per-time-window) the model maintains *ephemeral fast weights* — small adapter-like surfaces that update from the live interaction via a self-supervised objective. At session end, a replay/eval gate decides whether the ephemeral weights should be *promoted* to durable adapter weights (kept across sessions) or *discarded*. Most ephemeral weights are discarded; a few are promoted. Over time, the durable adapter bank grows from accumulated promotions. Closely related: Test-Time Training (Sun et al. 2020) and TTT-as-sequence-model (Sun et al. arXiv:2407.04620, NeurIPS 2024). Recent papers: *Test-Time Learning for Large Language Models* (TLM, arXiv:2505.20633, 2025), *VDS-TTT* (arXiv:2505.19475, 2025), *Test-Time Training Done Right* (LaCT, arXiv:2505.23884, 2025), *In-Place Test-Time Training* (arXiv:2604.06169, 2026).
- **Why the SoC's physical structure favors this loop.** Wave-1 named this Tier-3 because it has no CPT-scale receipts. Under the reframe:
  - Ephemeral fast weights live in DRAM, are small (LoRA-sized), and are *not* persisted unless promoted. → Matches small mutable working state + infrequent persistent write.
  - Promotion happens at session boundary, not per-token → infrequent batched persistent write.
  - The "self-supervised objective at test time" is forward-error-shaped, so most of the inner-loop compute is forward → Hexagon-friendly.
  - The durable adapter bank is a *growing collection of small parametric pieces*, which is a natural fit for UFS-resident, mmap-loaded, dynamically-routed adapter banks (mirrors the Multi-LoRA blind-spot wave-1 already named).
  - Wake/sleep version: ephemeral fast weights during the day, promotion + adapter consolidation at night.
- **Largest demonstrated scale.** *TTT as sequence model* (arXiv:2407.04620) demonstrates the architecture at sub-LLM scale; LaCT (arXiv:2505.23884) pushes chunk sizes to 1M tokens but uses fast-weights inside a fixed model, not for end-to-end pretraining. VDS-TTT (arXiv:2505.19475) shows +32.29% over a base model on domain adaptation via LoRA-only updates at test time. None of these is LLM pretraining — they are *adaptation on top of a pretrained base*. **No LLM pretrained under this loop exists.**
- **Corpus/data assumption.** Streaming. The "corpus" is the user's live interaction; the durable adapter bank is the cumulative compression of all sessions to date.
- **Training signal.** Self-supervised next-token prediction during test-time, or task-specific signals (verifier output for VDS-TTT). For promotion: held-out generalization on a small eval set, or comparison against a previous adapter's behavior.
- **Consolidation / persistence model.** Per-session ephemeral; per-promotion durable. Adapter bank grows monotonically (or with retirement / pruning). UFS is the natural backing store.
- **Hardware-fit risks.**
  - Per-session TTT inner-loop is still a backprop loop on the fast-weight surface. It is small (LoRA-sized), but it's still BP. If the fast-weight surface is too big, the inner loop becomes expensive.
  - Promotion gate quality. If the gate is wrong, durable adapters fill with noise. The gate is the central algorithmic problem.
  - Multi-LoRA routing complexity grows with adapter count.
  - The base model is still pretrained elsewhere. This loop does not *replace* CPT-style training of the base; it *extends* it with on-device adaptation. So strictly, this isn't an "alternative to CPT" — it's "what CPT becomes after the corpus is done."
- **Relationship to Polymath's stated ambition.** Most compatible with operator's distinction "this is training, not personalization." Under this loop the system is *training* by accumulating adapter promotions, but the substrate-level objective is still a pretrained base + a growing adapter bank. The risk is that this is the answer wave-1 already gave (MeBP + LoRA family) wearing more architectural clothing.
- **Falsifiers.**
  - F1: Promotion gate quality / specification. No principled answer exists.
  - F2: Per-session TTT inner-loop wall-clock + thermal cost on Hexagon/Adreno actually measured on SM8750. Unknown.
  - F3: Whether the durable adapter bank actually accumulates capability or just becomes a forgetting catastrophe.
  - F4: Whether the ratio "ephemeral discard : durable promote" is favorable enough that the loop is computationally cheap on average.
- **Key sources.** Sun et al. *TTT for OOD generalization* 2020. Sun et al. *Learning to (Learn at Test Time)* arXiv:2407.04620 (2024). LaCT arXiv:2505.23884 (2025). TLM arXiv:2505.20633 (2025). VDS-TTT arXiv:2505.19475 (2025). In-Place TTT arXiv:2604.06169 (2026). Awesome_Test_Time_LLMs at https://github.com/Dereck0602/Awesome_Test_Time_LLMs.

### 2.6 Self-supervised next-prediction with active sample selection

- **Loop structure.** Still next-token prediction. Still backprop. *But* a model selects which samples from a streaming corpus to actually train on, based on its own predicted uncertainty / value-of-information. Most samples are skipped. The "training corpus" effectively becomes "the samples the model believes will most improve it per unit compute." Often paired with self-distillation or curriculum learning.
- **Why the SoC's physical structure favors this loop.** The hard expense on this SoC is the persistent write (backward + optimizer + DRAM write). The forward, including evaluating "is this sample informative," is cheap. Active selection *shifts* compute from expensive persistent writes to cheap forward queries. Matches the SoC's asymmetry directly. Also: it lowers the effective tokens-per-unit-learning, meaning the SoC can converge with fewer DRAM-thrashing gradient steps.
- **Largest demonstrated scale.** This is the closest candidate in the document to actually being demonstrated at LM scale. Apple's *Language Models Improve When Pretraining Data Matches Target Tasks* (BETR, arXiv:2507.12466, 2025) shows benchmark-targeted selection beats random sampling at scale. Multi-actor collaboration for pretraining data selection (ACL 2025, https://aclanthology.org/2025.acl-long.466) shows +10.5% on standard benchmarks. Model-based filtering at multilingual scale (arXiv:2502.10361) shows 15% of training tokens matching baseline performance. **However, in all these papers the selection is done offline at corpus-curation time, by a separate model, with the actual training still being conventional CPT-on-curated-corpus.** True online active selection — the training model itself deciding what to train on next — is less mature.
- **Corpus/data assumption.** Either fixed-but-large (the model selects a curated subset) or streaming-and-large (the model is presented a firehose and chooses). Polymath corpus fits the former; a sensor / web / interaction stream fits the latter.
- **Training signal.** Next-token loss, but only on selected samples. Selection criteria: model uncertainty, perplexity-on-the-sample, gradient-norm-prediction, dissimilarity-from-already-trained-data, value-toward-downstream-benchmark.
- **Consolidation / persistence model.** Same as CPT — gradient update per processed sample. The savings are in *how many samples are processed*, not in *how each sample updates the model*.
- **Hardware-fit risks.**
  - Selection criterion compute. If "score the sample to decide whether to train on it" is itself a forward pass, then for selection ratios below ~10% the saved compute pays for the selection compute.
  - Distribution skew. Aggressive selection can over-focus on hard examples and degrade general capability — well-documented in active learning.
  - On a stream with non-stationarity, selection has to balance "is this informative" against "is this novel" — non-trivial.
- **Relationship to Polymath's stated ambition.** Most conservative reframe: still CPT, still corpus-shaped, still BP, still produces a model checkpoint. But re-tunes what "Polymath" optimizes: not "encode the corpus" but "encode the informationally-densest subset of the corpus per unit on-device compute." This loop changes the *optimization criterion*, not the *loop shape*. It is closest to wave-1's existing answer with a different scheduler.
- **Falsifiers.**
  - F1: Selection model and trained model converge to the same behavior, in which case selection self-confirms and the model never sees its true blind spots.
  - F2: Selection criterion's compute cost dominates the savings at the model scale of interest.
  - F3: On the actual SoC, the I/O cost of streaming through a corpus is high enough that selecting 10% of samples doesn't reduce I/O cost 10× (because UFS reads come in blocks).
- **Key sources.** BETR arXiv:2507.12466 (2025), Apple. Multi-actor collaboration arXiv:2410.08102 (ACL 2025). Multilingual model-based selection arXiv:2502.10361 (2025). Survey on Data Selection for LLM Instruction Tuning arXiv:2402.05123. Multilingual data mixtures arXiv:2510.25947 (2025).

### 2.7 Curriculum-driven CPT (still backprop, but with learned/adaptive sampling)

- **Loop structure.** Standard CPT but with a learned scheduler that picks token / domain / sequence ordering. The optimization is still ∂L/∂θ on a fixed corpus; the scheduler is a meta-model. Equivalent in spirit to the faculty/curriculum-scheduler architecture already in the operator's heterogeneous-SoC dialogue.
- **Why the SoC's physical structure favors this loop.** Slightly. The savings here are in *token efficiency*, not in *loop shape*. The SoC doesn't fundamentally care whether the corpus is shuffled or curriculum-ordered — the compute pattern is the same per step. The only fit advantage is that the CPU is a natural place for the scheduler to live (cheap on Phoenix L, not on Adreno's hot path).
- **Largest demonstrated scale.** Curriculum learning is a mature literature with mixed empirical results at LM scale. Recent: faculty-routing in LFM2 / OLMoE; data ordering in time-continual benchmarks (TiC-LM, ACL 2025). No definitive proof that curriculum-CPT beats randomly-shuffled CPT at frontier LM scale.
- **Corpus/data assumption.** Fixed-shape CPT corpus.
- **Training signal.** Standard CE loss.
- **Consolidation / persistence model.** Same as CPT.
- **Hardware-fit risks.** This is essentially the wave-1 first answer with a smarter scheduler. The risk is `fp-softrefusal`: claiming a paradigm shift while only retuning the existing one.
- **Relationship to Polymath's stated ambition.** Most direct continuation of wave-1. Lowest reframing.
- **Falsifiers.** Same as CPT.
- **Key sources.** TiC-LM arXiv:2025 ACL. *Investigating Continual Pretraining in LLMs* arXiv:2402.17400. CL of LLMs survey, ACM Computing Surveys 2025 (https://dl.acm.org/doi/10.1145/3735633).

**Note:** This candidate is included because it was named in the spec, but it is the weakest reframe in the set. Including it for completeness.

### 2.8 Energy-conserving learning rules

- **Loop structure.** Bound the magnitude of weight change per step by a physical energy budget. The optimizer is thermally aware: it scales the effective learning rate or the trainable-parameter mask based on the current device energy headroom. The training rule is *coupled* to the thermal state of the chip, not running as if energy were free.
- **Why the SoC's physical structure favors this loop.** The SoC is *physically* thermally constrained, has measurable energy budgets per workload, and has a long-running operation profile where steady-state energy budget matters more than burst budget. Wave-1's "energy-to-quality" authority metric explicitly named this. Energy-aware learning rules close the loop: instead of measuring energy *after* the run, the algorithm respects energy *during* the run.
  - Concretely: recent work on memristor training (TechXplore Jan 2026: error-aware probabilistic updates; "only 0.86 per thousand parameters required updates at any given step") and Energy-Aware Spike Budgeting for Continual SNN Learning (arXiv:2602.12236, 2025) demonstrate the principle on different substrates.
  - Energy-based local learning (PMC12418518, 2025) frames *local* update rules as natively energy-efficient because they avoid global gradient flow.
- **Largest demonstrated scale.** Small. Energy-aware optimization is a steady but small subfield. No LLM trained under explicit energy-budget constraints.
- **Corpus/data assumption.** Independent of corpus assumption. Energy-conserving rules can wrap any of 2.1–2.7.
- **Training signal.** Same as the underlying loop, modulated by an energy gate.
- **Consolidation / persistence model.** Same as the underlying loop, modulated.
- **Hardware-fit risks.** This is a *wrapper* on a loop, not a loop itself. The risk is that "energy-aware optimizer" reduces to "AdamW with adaptive LR + thermal throttle," which is what every mobile workload already does at the OS level. To be a real architectural choice, the energy budget has to gate the *learning signal*, not just the *clock speed*.
- **Relationship to Polymath's stated ambition.** A wrapper, not a primary architectural choice. But: if the authority metric is energy-to-target-quality (as the operator's prior docs state), then *not* having an energy-conserving rule is the wrong default. This candidate's "Should we use it?" question is closer to "How can any other candidate fail to use it?"
- **Falsifiers.**
  - F1: The wrapper effect is negligible compared to the underlying loop's properties.
  - F2: The energy gate is too crude to differentiate good updates from bad updates.
- **Key sources.** Memristor EaPU (Jan 2026 TechXplore release). Energy-Aware Spike Budgeting arXiv:2602.12236. Energy-aware deep learning on resource-constrained, https://anil.recoil.org/papers/2025-dl-rcn.pdf. Energy-based local learning, PMC12418518 (2025).

### 2.9 Discovered candidates (additions from this wave)

Three additional candidates came up while scanning that didn't appear in the spec's enumeration:

#### 2.9.1 Artificial Hippocampus Networks (AHN-style streaming compression)

- **Loop structure.** A learnable module compresses out-of-context-window information into a fixed-size compact long-term memory state. Operates inside the model, not outside. AHN is the explicit instantiation: ByteDance Seed, arXiv:2510.07318 (2025), uses Mamba2 / DeltaNet / GatedDeltaNet to recurrently compress streaming tokens.
- **Why SoC favors.** Forward-only (Mamba-style linear-attention recurrence) → Hexagon-friendly. Fixed-size memory → bounded DRAM. Streaming-native → matches the SoC stream profile. Replaces "store the corpus, sample from it" with "stream through the corpus once, compress as you go."
- **Scale.** Long-context modeling demonstrated; not yet 1B+ end-to-end-trained LM.
- **Relationship to Polymath.** Could be the *architecture* under which 2.1 (continual prediction) is implemented.

#### 2.9.2 Astrocyte-gated multi-timescale plasticity

- **Loop structure.** Couples fast eligibility traces (for temporal credit assignment), slow astrocytic gating (for stability), and a broadcast error signal (for task performance). Three timescales of plasticity on one network. PMC12886396 (2025), in deep SNNs.
- **Why SoC favors.** Multi-timescale matches the SoC's read/write tier asymmetry exactly: fast = DRAM cache, slow = DRAM, structural = UFS. Currently SNN-only; the principle generalizes.
- **Scale.** Small-scale.
- **Relationship to Polymath.** This is a *mechanism*, not a loop. It can be inserted into 2.1 or 2.4 as the actual plasticity rule.

#### 2.9.3 In-place TTT / KV-binding-as-linear-attention

- **Loop structure.** Test-time training implemented as in-place updates to the KV cache, which is mathematically equivalent to a form of linear attention. *Test-Time Training with KV Binding Is Secretly Linear Attention* (arXiv:2602.21204, 2026); *In-Place TTT* (arXiv:2604.06169, 2026).
- **Why SoC favors.** Updates are local to KV cache (small, in-DRAM, no DRAM thrashing for weight updates). Fits Hexagon's forward profile.
- **Scale.** Early.
- **Relationship to Polymath.** Suggests a *third class* of fast-weight surface: not LoRA, not full weights, but the KV cache itself. Architecturally novel.

---

## 3. Cross-cut: which loop most cleanly optimizes information density per token?

This was the synthesis question between this agent and the information-theoretic envelope agent. Per-candidate information-per-token argument:

| Loop | Info-per-update token | Notes |
|---|---|---|
| CPT (baseline) | Low. Every token contributes a small gradient irrespective of novelty. Most tokens are redundant. | This is the baseline being measured against. |
| 2.1 Continual prediction + selective consolidation | High. By construction, only surprising/valuable tokens drive weight updates. Each persistent write is high-info by gating. | Closest to "info per persistent write" maximization. |
| 2.2 Online TD | Low-to-medium. Each step contributes a TD error of variable size. High variance. | Sample-inefficiency problem dominates. |
| 2.3 World model | Medium-high. World model captures *predictable* structure → updates concentrate where the model is currently wrong. | JEPA latent prediction is strictly higher info-per-byte than pixel reconstruction. |
| 2.4 Sleep replay | High at sleep, zero at wake. Time-averaged info-per-update is high because replay selects high-value memories. | The selection of *what to replay* is the info-per-update lever. |
| 2.5 TTT with replay-gated promotion | Per-promotion: very high. Per-ephemeral-step: low-medium (BP on user data). | Promotion gate is the info filter. |
| 2.6 Active sample selection | High. Direct optimization of info-per-train-token. | Most directly measurable. Empirically validated at scale (BETR). |
| 2.7 Curriculum CPT | Medium. Re-ordering improves convergence rate but not asymptotic info-per-token. | Smallest gain. |
| 2.8 Energy-conserving rule | Independent. Wraps any loop. | The energy axis is *bytes per joule* not bytes per token. |

The information-theoretic envelope question — *if the phone is information-bound, the natural loop optimizes information density per token* — favors **2.1 (continual prediction + selective consolidation)** and **2.6 (active sample selection)** most cleanly. 2.4 and 2.5 are close. 2.7 is the weakest under this lens.

Notice 2.1 and 2.6 are very different shapes (streaming, brain-inspired vs offline curation + CPT). The two ends are: 2.6 is *the maximal information-density answer assuming the loop must remain CPT-shaped*; 2.1 is *the maximal information-density answer if the loop can be restructured*. The wave-1 frame implicitly chose the first; this wave's reframe permits the second.

---

## 4. The relationship to Polymath's stated ambition

This is the question the spec asks be surfaced openly without resolution:

**Could it be that Polymath should NOT be a corpus-compression model in the first place?**

Three honest readings, none chosen:

**Reading A — Polymath stays a corpus-compressed LM.** Wave-1 was right under this reading. The corpus is fixed (Polymath multilingual + multi-domain), the objective is to encode it, the loop is some flavor of BP-on-fixed-corpus. Wave-2's contribution under this reading is to suggest that the loop should use 2.6 (active sample selection) or 2.7 (curriculum) wrapped in 2.8 (energy budget) — i.e. *the same answer wave-1 gave, tuned for the SoC's energy/thermal axis more aggressively*. The reframe in this case is marginal.

**Reading B — Polymath is a continual predictor over a stream that includes the Polymath corpus.** The corpus seeds the loop, but the artifact is *the trained system after weeks/months of streaming operation*. The system includes a stable trunk (corpus-shaped knowledge), a plastic surface (recent context), an episodic memory (selected events), and a scheduler. The Polymath corpus becomes one input among others — eventually small relative to the cumulative stream. The artifact is *not a checkpoint of weights*; it is a *long-running cognitive system*. 2.1, 2.4, 2.5 fit this reading.

**Reading C — Polymath is a policy/world-model that has consumed the Polymath corpus as one of its training environments.** The deepest reframe. The artifact is an agent: actor + value/world-model. Its "training" is its interaction with environments, one of which includes the corpus. The corpus becomes a textbook, not the target. 2.2 and 2.3 fit this reading.

Which reading is right depends on:
- What the deployment scenario actually is. If Polymath is an in-pocket assistant interacting with a user, B or C are favored. If Polymath is a producible LM checkpoint for evaluation against held-out corpora, A is favored.
- What the operator means by "this is training, not personalization." Reading A says corpus-side training. Reading B says lifelong streaming training. Reading C says interaction-side training. All three are honestly "training" in different senses.
- Whether the authority metric is "perplexity on held-out Polymath corpus" (A), "capability that emerges after sustained operation" (B), or "policy quality on user tasks" (C).

This document does *not* resolve which reading. The wave-1 answer correctly maximizes Reading A. If Reading A is correct, wave-2's reframe was an interesting digression but not load-bearing. If Reading B or C is correct, wave-1's ranking was wrong-frame and a re-ranking is required.

The fact that the SoC's physical signature favors Reading B / C over Reading A is the substantive architectural claim of this document. It is *not* a recommendation. It is an *unresolved tension* between substrate intent and corpus-shaped ambition.

---

## 5. Honest verdict on the wave-1 anchoring

Wave-1 ranked pipeline-parallel BP, MeBP + MobiZO, and ZeroQAT as Tier-1 because they have CPT-scale receipts. **Under the CPT-shaped-objective frame, that ranking is correct and remains correct.** Wave-2 does not contest those receipts.

But the spec asks: *is CPT-shaped-objective the right frame?* Under Reading A above, yes. Under Readings B or C, no.

Three specific places where wave-1's analysis would re-rank under a streaming/continual frame:

- **MeBP + MobiZO promoted further.** Already named in wave-1 Tier-1. Under the streaming reframe, ZO is even more natural because it fits a continual prediction loop where "weight update per sample" is the exception, not the rule. The ZO forward-only character is *only* a workaround for "can't do backprop on Hexagon" under wave-1; under wave-2 it is the natural shape of *should not do backprop most of the time anyway*.
- **Test-time training with replay-gated promotion** (wave-1 Tier-3 blind-spot item #7) is *the explicit loop family for Reading B*. It belongs higher under the reframe — possibly the most direct match for "the operator-named architectural intent" because it preserves a corpus-shaped pretrained base while replacing the per-token CPT loop with session-scoped TTT + sleep-promotion. The wave-1 ranking of Tier-3 reflects *CPT scale receipts*, not loop fit.
- **Sleep-replay-style consolidation** doesn't appear in wave-1's ranking at all. Under the reframe it is among the cleanest hardware-loop fits in the entire candidate set. Its placement at "doesn't even rank" in wave-1 is the most consequential omission this wave found.

**Honest single-line verdict on the wave-1 anchoring:** The wave-1 anchoring is the correct first answer for Reading A and the wrong first answer for Readings B and C. Without picking a reading (which is the synthesis agent's job, not this agent's), wave-1's ranking should be treated as a strong upper bound on "what answer survives CPT framing" and a weak upper bound on "what answer the SoC's design intent actually favors."

---

## 6. Open tensions (places where this reframe forces unresolved questions)

1. **The corpus question.** If the Polymath corpus is the input, the loop is constrained to corpus-shaped training and wave-1's frame is right. If the input is a *stream* (sensory, user-interaction, world-derived), then 2.1, 2.2, 2.3, 2.4 are natural and wave-1's frame is wrong. The corpus-vs-stream choice is upstream of every other choice in this document. It has not been made.

2. **The "Polymath as artifact" question.** Is Polymath a *weight checkpoint* (deliverable as a file)? A *running cognitive system* (deliverable as a phone)? A *policy* (deliverable as a behavior)? The artifact specification is upstream of the loop specification, and the operator's stated ambition (`docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`) is consistent with all three.

3. **The scale question.** Every non-CPT loop in this document has sub-1B published demonstrations. The wave-1 ranking treats this as a hard disqualifier. The reframe treats it as a *possibly correct* disqualifier (we may genuinely be the wrong scale of organization to break this barrier) and a *possibly mis-framed* disqualifier (the loops have not been tried at scale because the cloud GPU substrate disincentivizes them; the SoC substrate may incentivize them and produce a different scaling story). This tension is not resolvable from the literature alone.

4. **The "but it's still backprop" question.** Several candidates here use BP internally (TTT inner loop, world-model update step, JEPA training, replay-phase distillation). They are non-CPT-loop-shapes that still use BP somewhere. Is that "still backprop, just better optimizer" (forbidden in spec) or is it "BP as a kernel inside a loop that is itself structurally different"? Honest answer: the difference is real but the boundary is fuzzy. The candidates where the loop is *most* different from CPT (2.1, 2.4) tend to use the *least* BP (local Hebbian, contrastive distillation); the ones with most BP inside (2.5 TTT, 2.7 curriculum) reframe least.

5. **The "no sensor stream" question.** If Polymath does not consume a real sensor / interaction stream — i.e. the device sits next to the operator but doesn't actually integrate the operator's life — then 2.1, 2.2, 2.3 are robbed of their natural input. The wave-1 frame is implicitly correct in that case. The substrate then becomes "an underutilized SoC running CPT-on-a-corpus," and the device's sensor/embodiment advantage is irrelevant. This is the operator's choice to make explicit.

6. **The "the device is the artifact" question.** Under Reading B / C, the device + its weights + its accumulated state *as a system* is the result. You cannot ship that artifact in the way you ship a model card. You can ship "the device" or "a snapshot of its state." This is a deployment-and-distribution question that wave-1 did not have to answer because Reading A's checkpoint-is-the-artifact assumption was implicit.

---

## 7. Falsifiers per candidate loop family (compact recap)

- **2.1 Continual prediction + selective consolidation:** F1 trunk consolidation too slow for overnight; F2 no real stream; F3 surprise-gate pathology; F4 no LM-scale demonstration by 2027.
- **2.2 Online TD:** F1 sample budget; F2 reward source; F3 exploration safety; F4 quality ceiling vs pretrained base.
- **2.3 World model:** F1 no generative LM-scale demonstration; F2 imagined-rollout cost on phone; F3 no real environment.
- **2.4 Sleep replay:** F1 local-rule quality ceiling; F2 wake/sleep scheduling; F3 buffer selection; F4 no LM-scale demonstration.
- **2.5 TTT + replay-gated promotion:** F1 promotion gate; F2 measured TTT cost; F3 adapter accumulation pathology; F4 reduce-to-existing-LoRA.
- **2.6 Active sample selection:** F1 selection self-confirming; F2 scoring cost; F3 I/O-block granularity.
- **2.7 Curriculum CPT:** Same as CPT. (Reframe is shallow.)
- **2.8 Energy-conserving rule:** F1 wrapper effect negligible; F2 gate too crude.

The substrate-level falsifier that affects every non-CPT candidate above is:

**Sf:** A measurement on actual SM8750 hardware of a continual / streaming / sleep-replay loop *at any model scale* showing competitive perplexity / capability per joule per hour vs a CPT-trained baseline of the same on-device compute budget. If no such measurement is producible within ~6 months, the non-CPT reframe remains a research bet without empirical anchor. Wave-1's answer would then be defensibly the right *first* answer even if not the right *terminal* answer.

---

## 8. Sources

### Continual prediction / hippocampus-cortex / CLS
- McClelland, McNaughton, O'Reilly. "Why there are complementary learning systems in the hippocampus and neocortex." *Psychological Review* 1995.
- Kumaran, Hassabis, McClelland. "What learning systems do intelligent agents need? Complementary Learning Systems Theory updated." *Trends in Cognitive Sciences* 2016.
- van de Ven, Siegelmann, Tolias. "Brain-inspired replay for continual learning with artificial neural networks." *Nature Communications* 2020. https://www.nature.com/articles/s41467-020-17866-2
- Tadros, Krishnan, Ramyaa, Bazhenov. "Sleep-like unsupervised replay reduces catastrophic forgetting in artificial neural networks." *Nature Communications* 2022. https://www.nature.com/articles/s41467-022-34938-7
- HiCL: Hippocampal-Inspired Continual Learning. arXiv:2508.16651 (2025). https://arxiv.org/html/2508.16651v1
- Semi-parametric Memory Consolidation: Towards Brain-like Deep Continual Learning. arXiv:2504.14727 (2025). https://arxiv.org/html/2504.14727v1
- SCM: Sleep-Consolidated Memory with Algorithmic Forgetting for Large Language Models. arXiv:2604.20943 (2026). https://arxiv.org/html/2604.20943v1
- "A model of autonomous interactions between hippocampus and neocortex driving sleep-dependent memory consolidation." *PNAS* 2022. https://www.pnas.org/doi/10.1073/pnas.2123432119
- "Prediction errors disrupt hippocampal representations and update episodic memories." *PNAS* 2021. https://www.pnas.org/doi/10.1073/pnas.2117625118
- "Systems memory consolidation during sleep: oscillations, neuromodulators, and synaptic remodeling." PMC12576410.
- "Sleep prevents catastrophic forgetting in spiking neural networks by forming a joint synaptic weight representation." *PLOS Computational Biology* 2022.
- "Interleaved Replay of Novel and Familiar Memory Traces During Slow-Wave Sleep Prevents Catastrophic Forgetting." PubMed 40667278.
- Sleep Replay Consolidation, AAAI 2025.
- NeuroDream: A Sleep-Inspired Memory Consolidation Framework for Artificial Neural Networks. SSRN 5377250 (2025).
- "A recurrent network model of planning explains hippocampal replay and human behavior." *Nature Neuroscience* 2024.

### Online RL / TD / process reward models
- Sutton & Barto. *Reinforcement Learning: An Introduction* 2018.
- "Discovering state-of-the-art reinforcement learning algorithms." *Nature* 2025. https://www.nature.com/articles/s41586-025-09761-x
- Process Reward Models for LLM Agents. arXiv:2502.10325 (2025).
- AgentRM: Enhancing Agent Generalization with Reward Models. ACL 2025. https://aclanthology.org/2025.acl-long.945.pdf
- Meta-RL Induces Exploration in Language Agents. arXiv:2512.16848 (2025).
- "How Should We Meta-Learn Reinforcement Learning Algorithms?" arXiv:2507.17668 (2025).
- Review of Reinforcement Learning for Large Language Models. http://www.liziniu.org/docs/RL4LLM_Survey.pdf
- Comprehensive Survey of RL for LLMs, arXiv:2411.18892 (2025).
- Training Recipes for Agentic RL in LLMs: A Survey. https://github.com/blacksnail789521/Agentic-RL-Training-Recipes

### World models / JEPA / Dreamer
- Ha & Schmidhuber. "World Models." arXiv:1803.10122 (2018).
- Hafner et al. "Dream to Control: Learning Behaviors by Latent Imagination" 2019.
- Hafner et al. DreamerV3, *Nature* 2025.
- Hafner et al. Dreamer 4. arXiv:2509.24527 (Sept 2025).
- Assran et al. I-JEPA (Meta, 2023).
- V-JEPA, V-JEPA 2 (Meta, 2025), V-JEPA 2.1 (Meta, March 2026).
- "Understanding World or Predicting Future? A Comprehensive Survey of World Models." arXiv:2411.14499 / *ACM Computing Surveys* 2025.
- "A Comprehensive Survey on World Models for Embodied AI." arXiv:2510.16732 (2025).
- "From Curiosity to Competence: How World Models Interact with the Dynamics of Exploration." arXiv:2507.08210 (2025).
- Pathak et al. "Curiosity-driven Exploration by Self-supervised Prediction." arXiv:1705.05363 (2017).
- VL-JEPA: Joint Embedding Predictive Architecture for Vision-language. arXiv:2512.10942 (2026).
- JEPA for RL. ESANN 2025. https://www.esann.org/sites/default/files/proceedings/2025/ES2025-19.pdf

### Test-time training / fast weights
- Sun et al. "Test-Time Training for OOD Generalization" 2020.
- Sun et al. "Learning to (Learn at Test Time): RNNs with Expressive Hidden States." arXiv:2407.04620 (NeurIPS 2024).
- LaCT: "Test-Time Training Done Right." arXiv:2505.23884 (2025).
- TLM: "Test-Time Learning for Large Language Models." arXiv:2505.20633 (2025).
- VDS-TTT: "Continuous Self-Improvement of LLMs by Test-time Training with Verifier-Driven Sample Selection." arXiv:2505.19475 (2025).
- "Test-Time Training with KV Binding Is Secretly Linear Attention." arXiv:2602.21204 (2026).
- "In-Place Test-Time Training." arXiv:2604.06169 (2026).
- "The Surprising Effectiveness of Test-Time Training for Abstract Reasoning." arXiv:2411.07279 (2024).
- Awesome_Test_Time_LLMs collection: https://github.com/Dereck0602/Awesome_Test_Time_LLMs

### Active sample selection / data curation at scale
- "Language Models Improve When Pretraining Data Matches Target Tasks" (BETR). arXiv:2507.12466 (2025). Apple.
- "Efficient Pretraining Data Selection for Language Models via Multi-Actor Collaboration." ACL 2025. https://aclanthology.org/2025.acl-long.466
- "Enhancing Multilingual LLM Pretraining with Model-Based Data Selection." arXiv:2502.10361 (2025).
- "Revisiting Multilingual Data Mixtures in Language Model Pretraining." arXiv:2510.25947 (2025).
- "A Survey on Data Selection for LLM Instruction Tuning." arXiv:2402.05123.

### Streaming / continual / lifelong LM pretraining
- "Continual Learning of Large Language Models: A Comprehensive Survey." *ACM Computing Surveys* 2025. https://dl.acm.org/doi/10.1145/3735633
- "Investigating Continual Pretraining in Large Language Models: Insights and Implications." arXiv:2402.17400.
- TiC-LM: "A Web-Scale Benchmark for Time-Continual LLM Pretraining." ACL 2025. https://aclanthology.org/2025.acl-long.1551.pdf
- "Self-Evolving LLMs via Continual Instruction Tuning." arXiv:2509.18133 (2025).
- "Continual Learning in Large Language Models: Methods, Challenges, and Opportunities." arXiv:2603.12658 (2026).
- LiveCC: Learning Video LLM with Streaming Speech Transcription at Scale. CVPR 2025.

### Energy-bounded / thermally-aware learning rules
- "Energy-Aware Spike Budgeting for Continual Learning in Spiking Neural Networks for Neuromorphic Vision." arXiv:2602.12236 (2026).
- Memristor EaPU training method (~6 orders of magnitude energy reduction). TechXplore Jan 2026. https://techxplore.com/news/2026-01-memristor-method-slashes-ai-energy.html
- "Effective methods and framework for energy-based local learning of deep neural networks." PMC12418518 (2025).
- "Energy-Aware Deep Learning on Resource-Constrained Computing Networks." https://anil.recoil.org/papers/2025-dl-rcn.pdf
- "Measuring the Energy Consumption and Efficiency of Deep Neural Networks." arXiv:2403.08151 (2024).

### Discovered candidates
- AHN: Artificial Hippocampus Networks for Efficient Long-Context Modeling. arXiv:2510.07318 (2025). ByteDance Seed.
- "Astrocyte-gated multi-timescale plasticity for online continual learning in deep spiking neural networks." PMC12886396 (2025).
- "Artificial Hippocampus Networks" repo: https://github.com/ByteDance-Seed/AHN

### Project-internal priors (referenced through this document)
- `/Users/Zer0pa/Polymat AI/Polymath-AI/RESISTANCE-V2.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/nature-physics-learning-paradigms.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/hexagon-training-investigation.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/heterogeneous-training-loop-shape.md`

---

## 9. One-paragraph TL;DR (for orchestrator handoff)

Wave-1 anchored on "scale CPT-shaped backprop on a fixed corpus" and concluded pipeline-parallel BP + MeBP + MobiZO + ZeroQAT. That conclusion is correct under its frame. The SoC's design intent — forward-strong accelerator, small mutable cache, expensive infrequent persistent write, hours-to-days sustained operation, embedded in a sensory stream — reads as **continual-streaming-learning hardware**, not as **fixed-corpus-CPT hardware**. Under that reframe, at least five candidate loop families (continual prediction with selective consolidation; online TD; world-model loops; sleep-replay-style wake/sleep training; test-time training with replay-gated promotion) fit the substrate more cleanly than CPT-shaped BP does. None have LLM-scale receipts; that is the cost of the reframe. The reframe surfaces a genuine open tension: if Polymath is *a corpus-compressed LM checkpoint*, wave-1 is right; if Polymath is *a long-running predictive system that consumes the corpus as one of its inputs*, wave-1 is wrong-frame and the ranking is unrecognizable. The substrate's signature favors the second reading. This document does not pick a reading and does not pick a loop — both are synthesis decisions. It surfaces the candidates, names what the SoC physically wants, names the falsifiers, and refuses to collapse to "still backprop, just better optimizer" (the wave-1 answer that prompted this wave) or to "small Forward-Forward on MNIST" (the demo-gravity trap). The biggest single architectural finding is that **sleep-replay-style consolidation does not appear anywhere in the wave-1 ranking, and it is among the cleanest hardware-loop fits in the entire candidate set, including the operator-named "phone thinks overnight" property as a literal design match**. That omission is the most consequential blind spot wave-1's frame had. The synthesis agent now decides whether the reframe is load-bearing — i.e. whether Polymath is in Reading A's world or in Readings B/C's world. If Reading A, wave-1 stands. If Readings B or C, wave-2 forces a re-ranking with sleep-replay consolidation, continual prediction with selective consolidation, and TTT-with-replay-promotion among the top candidates, none with current LM-scale proof.
