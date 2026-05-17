# Nature/Physics/Information-Theory Learning Paradigms vs Backprop on Heterogeneous SoC

**Date:** 2026-05-16
**Role:** Research Agent (Polymath-AI lane)
**Substrate:** RedMagic 10 Pro Plus, Snapdragon 8 Elite SM8750, 24 GB shared LPDDR5X, ~85 GB/s, Adreno 830, Hexagon NPU. Dedicated AI training appliance, sustained-throughput priority, latency is not the gate.
**Discipline:** Resistance V2. Authority metric: "trains an LLM-scale model on this SoC to comparable or better quality than backprop, within the energy/thermal envelope, with reproducible receipts." Mathematical elegance and hardware fit do not substitute for empirical scale.
**Question:** which physics-, biology-, or information-theoretic learning paradigms have a real structural fit with the SoC and are credible at LLM scale?

## Verdict

The honest answer is uncomfortable for the "nature/physics-inspired" frame. **Of the 13 paradigm families investigated, zero have demonstrated LLM-scale training (1B+ parameter language models trained from scratch or via continued pretraining to comparable quality as backprop) outside of the standard backprop family.** Predictive coding, equilibrium propagation, forward-forward, modern Hopfield/EBM, resonator/oscillator learning, FEP/active inference, SoftHebb/three-factor, reservoir computing, and synthetic gradients all top out somewhere between MNIST and small ResNet/ImageNet 32×32. SpikingBrain-76B is the only "biologically inspired" model approaching LLM scale, and on close reading it is a Qwen2.5-7B-derived sparsity-and-linear-attention reshape trained on a non-NVIDIA GPU cluster, not a phone, not a fundamentally different update rule (https://arxiv.org/abs/2509.05276).

Given Resistance V2, the only paradigms worth experimental investment on the SM8750 right now are the three that have *either* LLM-scale receipts *or* a direct SoC fit that the orchestrator can verify on this phone in weeks, not years:

**Tier-1 (first-wave, fund the experiment):**

1. **Bubble-aware pipeline-parallel backprop with split-backward (Zero-Bubble / ZB-V / 1F1B-V variants)** plus per-stage device choice (NPU forward island, GPU/CPU trainable strip).
   - **Why first-wave:** mathematically *is* backprop, so no quality risk. Direct SoC fit: CPU control, GPU flexible compute, NPU forward island all play their physical role; sustained throughput priority matches phone-as-appliance framing.
   - **Falsifier:** if scheduler/sync overhead and NPU↔GPU↔CPU memory contention erase the wall-clock benefit vs single-device GPU baseline at any model size we care about (1B-7B).
   - **Reason it could beat backprop on this SoC:** it *is* backprop. The win is utilization of three devices instead of one without bubble cost. ZB-1F1B reports 15-31% throughput vs 1F1B at the same memory budget (https://arxiv.org/abs/2401.10241).
   - **References:** ZB (https://arxiv.org/abs/2401.10241); AdaPtis for heterogeneous pipelines (https://arxiv.org/pdf/2509.23722); Seq1F1B (https://aclanthology.org/2025.naacl-long.454.pdf); PipeFill for bubble exploitation (https://www.pdl.cmu.edu/PDL-FTP/BigLearning/Pipefill-2410.07192v1.pdf).

2. **Memory-rematerialized first-order backprop on trainable surfaces (MeBP-class) + zeroth-order surrogate (MobiZO/MeZO/AGZO) for forward-only adapter updates.**
   - **Why first-wave:** these are the two methods with measured numbers on the actual Snapdragon 8 Elite / OnePlus 12 / iPhone class. MobiZO measured 5.76 s/step at seq=128 batch=16 on OnePlus 12 Hexagon NPU for TinyLlama-1.1B, beat first-order LoRA-FA by up to 8.1% accuracy at comparable memory (https://arxiv.org/html/2409.15520v3). ZeroQAT fine-tuned a 6.7B model on a OnePlus 12 (https://arxiv.org/abs/2509.00031). MeBP reports sub-1 GB fine-tuning memory for 0.5-4B LLMs on iPhone 15 Pro Max (https://arxiv.org/abs/2510.03425).
   - **SoC fit:** ZO uses only forward passes — NPU's strength. MeBP rematerializes activations — trades NPU forward repeat against GPU/CPU backward memory.
   - **Falsifier:** if examples/sec-to-target-quality under sustained thermal state loses to bubble-aware pipeline backprop on the same Qwen3-4B or Gemma 4 E2B base, both methods drop to second-class for primary training and survive only as adapter/calibration surfaces.

3. **Quantization-aware on-device training (ZeroQAT and successors)** as the *paradigm-level* counter-bet against assuming Q4 weights are immutable.
   - **Why first-wave:** mobile NPU compute is INT4/INT8-shaped. Training the actually-deployed quantized graph (rather than fp/bf and quantizing after) closes the train-deploy gap. ZeroQAT does this forward-only.
   - **SoC fit:** matches what the NPU can actually run; no fictional fp32 inner loop.
   - **Falsifier:** if forward-query count and dequant/quant boundary overhead make wall-clock-to-quality worse than PTQ + adapter training.

**Tier-2 (research-viable, fund probes, not the main line):** holomorphic equilibrium propagation (only paradigm besides PC with a published "matches backprop on ImageNet 32×32" claim, https://arxiv.org/abs/2209.00530); SoftHebb/Hebbian-deep-learning-without-feedback as an unsupervised feature-learning probe (27.3% ImageNet top-1 with 5 hidden layers, https://arxiv.org/abs/2209.11883); μPC for deep-residual classifiers as a sanity experiment (https://arxiv.org/abs/2505.13124).

**Tier-3 (speculative, do not fund without an explicit physical-hardware partner):** forward-forward, deep oscillatory networks, free energy principle / active inference, adaptive resonance theory, reservoir computing, synthetic gradients, spike-based.

The operator-mentioned "resonance-based" candidate **does not currently exist as a real LLM-scale family**. See dedicated section below.

### Rubric used

For each candidate the score is on four axes:

- (a) **Scale evidence**: largest credible model trained end-to-end with comparable quality to backprop. Anchor scale at **language models ≥1B parameters**, since that is the Polymath target.
- (b) **SoC structural fit**: which hardware element (NPU forward, GPU flexible, CPU control, unified memory, sustained throughput) it physically favors.
- (c) **Distance to backprop**: close (mathematically equivalent or surrogate of) = low risk; far (different objective) = potential breakthrough, higher risk.
- (d) **Engineering cost on SM8750**: how many engineer-weeks to a first decisive measurement under Resistance V2.

| Paradigm | (a) Scale evidence | (b) SoC fit | (c) Distance from backprop | (d) Eng. cost | Tier |
|---|---|---|---|---|---|
| Pipeline-parallel backprop (ZB-V, AdaPtis) | LLM-scale GPU cluster, datacenter receipts | Direct: 3 devices × split-backward | Identical objective | Low (existing kernels + scheduler) | **1** |
| MeBP / MobiZO / ZeroQAT (FO+ZO on phone) | Measured on OnePlus 12, TinyLlama-1.1B, 6.7B QAT | Direct: NPU forward + small trainable strip | Surrogate (ZO) / identical (MeBP) | Low (existing repos) | **1** |
| Quantization-aware on-device training | 6.7B on OnePlus 12 | Direct: matches NPU INT format | Surrogate | Low | **1** |
| Holomorphic Equilibrium Propagation | ImageNet 32×32, ResNet-class | Settling = repeated forward, NPU-friendly in theory | Provable backprop equivalence in limit | Medium-high (no LLM proof) | 2 |
| μPC (Predictive Coding) | MNIST/Fashion-MNIST, 128-layer residual | Local per-layer compute, NPU-island-per-layer in theory | Equivalent to BP under fixed-prediction assumption | Medium-high (no transformer/LM proof) | 2 |
| SoftHebb / Hebbian no-feedback | 5-layer CNN, 27.3% ImageNet | Per-layer local, NPU-friendly | Different objective (no global error) | Medium (feature learning only) | 2 |
| Forward-Forward (+CwComp/DeeperForward/CFF) | CIFAR-10/100 with effort, ViT only marginally | NPU-pure: no backward kernel needed | Different objective | Medium-high; LM unproven | 3 |
| Modern Hopfield / EBM (CD/Langevin) | Image generation, not LM pretraining | Settling = forward repeat | Different objective | High (no LM track record) | 3 |
| Deep Oscillatory / coupled-oscillator / Ising | Sentiment 85% IMDB, no LLM | Needs analog or specialty digital; SM8750 has no oscillator fabric | Different objective | High (no SoC primitive) | 3 |
| Free Energy Principle / active inference | No LM weight-training evidence; rhetorical | Aligns with phone-as-agent narrative, but no algorithm | Predictive-coding-equivalent in deep nets | High (no algorithm-as-trainer at LM scale) | 3 |
| Adaptive Resonance Theory | Incremental classifiers; "MemoryART" is LLM memory layer, not training | None (architectural, not training) | Different paradigm | High (not a training rule) | 3 |
| Reservoir Computing / ESN | 100M-word grammaticality competitive; not LM-scale generation | Frozen reservoir + linear readout — NPU-friendly | Different objective (random recurrent) | Medium (cheap to try but no LM ceiling) | 3 |
| Synthetic Gradients / DNI | RNN/CNN historical only, no 2024-2025 LM scaling | Decouples updates across CPU/GPU/NPU | Surrogate (predicted gradient) | Medium (drift risk known) | 3 |
| Spiking (SpikeGPT, SpikeLLM, SpikingBrain-76B) | 76B on MetaX GPU cluster — not phone | Wants neuromorphic substrate; SM8750 has no spike fabric | Different at compute level, similar at training | High on this SoC | 3 |
| Information Bottleneck / MDL / HSIC | Theory/regularizer, not weight-update rule | None specific | Not a different training rule | N/A as primary trainer | not applicable |

The rubric collapses to: **only methods with measured numbers on a Snapdragon-class phone (MeBP, MobiZO, ZeroQAT) and bubble-aware backprop schedules satisfy Resistance V2's authority gate today.** Everything else is research-viable at best.

---

## Per-paradigm analysis (six questions each)

For each: (1) math; (2) largest empirical scale (paper, model, task, year); (3) equivalence to backprop; (4) SoC fit; (5) falsifiers; (6) 2025-2026 progress.

### 1. Predictive Coding (PC)

1. **Math.** Each layer maintains value units `x_l` and error units `eps_l = x_l - f(W_l x_{l-1})`. Energy `E = sum_l ||eps_l||^2`. Inference (E-step): iteratively settle `x_l` to minimize `E` while clamping input/output. Learning (M-step): `dW_l / dt = -dE/dW_l = eps_l f'(W_l x_{l-1}) x_{l-1}^T`. Update uses *only locally available* signals from neighboring layers.
2. **Largest empirical scale.**
   - Whittington & Bogacz, *NeurIPS 2017*, *Neural Computation* 2017 — small MLPs (https://pmc.ncbi.nlm.nih.gov/articles/PMC8970408/).
   - Salvatori et al., 2022 — PC for transformers, sentence-level only.
   - Millidge et al., *Neural Computation* 35(12) 2023 — critical evaluation (https://direct.mit.edu/neco/article/35/12/1881/117833/).
   - Song et al., "On the relationship between PC and BP," *PLOS One* 2022 — PC equals BP under fixed-prediction assumption (https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0266102).
   - Pinchetti et al., 2024 — posed scaling as community challenge.
   - **μPC, Innocenti et al., arXiv:2505.13124, NeurIPS 2025** — reliably trains *up to 128-layer residual MLPs* on **MNIST and Fashion-MNIST only**. ~98% MNIST in 5 epochs; ~89% Fashion-MNIST in <15 epochs. **Authors explicitly state**: "Future work could also study whether μPC provides any compute or memory efficiencies over BP." Not tested on transformers (https://arxiv.org/html/2505.13124v1).
   - VERSES "Benchmarking PC Networks Made Simple" — largest is ResNet18; matches BP on small CNNs, *degrades* on ResNet18 (https://www.verses.ai/research-blog/benchmarking-predictive-coding-networks-made-simple).
3. **Equivalence to backprop.** Provably equivalent in the fixed-prediction limit (Song et al. 2022). In practice, finite settling iterations give an approximation whose bias is empirically measured to be small for shallow nets but grows with depth.
4. **SoC fit.** *Conceptually attractive*: each layer's forward + local error computation can run on a separate NPU island; CPU orchestrates settling; no global backward kernel required. In practice, settling = many forward repeats per step (typically 8-64), so the NPU forward-throughput advantage is partially consumed.
5. **Falsifiers.**
   - No published PC training of a 1B+ language model. If μPC family does not produce a transformer LM at ≥125M parameters with competitive perplexity in 2026, the "PC scales" claim has failed.
   - Settling steps × forward cost must beat (forward + backward + optimizer) per BP step in wall-clock. Has not been measured at LM scale.
6. **2025-2026 progress.** μPC (May 2025) is the most concrete scaling result; restricted to deep residual MLPs on tiny image data. VERSES is actively pushing the engineering, but no LM proof yet.

**Verdict: Tier 2. Research-viable as a sanity probe on small CNNs/ResNets on Adreno. Not a first-wave Polymath bet.**

### 2. Equilibrium Propagation (EP)

1. **Math.** Energy-based recurrent network with state `s` and energy `E(s, x, theta)`. **Free phase**: settle `s_*` to local minimum of `E(s, x, theta)`. **Nudged/clamped phase**: settle `s_*(beta)` of `E + beta L(s, y)` for small `beta`. **Local update**: `dtheta = (1/beta) (dE/dtheta|_{s_*(beta)} - dE/dtheta|_{s_*})`. Reduces to BP gradient in the limit `beta -> 0` (Scellier & Bengio, *Frontiers Comp. Neuro.* 2017).
2. **Largest empirical scale.**
   - **Holomorphic EP, Laborieux & Zenke, arXiv:2209.00530, 2022** — first benchmark on **ImageNet 32×32**, matches BP performance using "finite Fourier coefficient" trick to extract exact gradient (https://arxiv.org/abs/2209.00530).
   - **Hopfield-Resnet13 on CIFAR-10, "Scaling EP to Deeper Networks," arXiv:2509.26003, 2025** — 93.92% CIFAR-10, comparable to ResNet-13 BP, claims "nearly twice prior depth" (https://arxiv.org/html/2509.26003v1).
   - **Intermediate Error Signals, arXiv:2508.15989, 2025** — addresses vanishing gradient (https://arxiv.org/html/2508.15989v1).
   - **Directed EP Revisited, Mathematics 13(11) 2025** (https://www.mdpi.com/2227-7390/13/11/1866).
   - **Improving EP without Equilibrium, ICLR 2024** (https://proceedings.iclr.cc/paper_files/paper/2024/file/6a55f024db3f771194bdadc8f3a35381-Paper-Conference.pdf).
   - **No published transformer or language model trained by EP.** No 1B-parameter EP model anywhere.
3. **Equivalence to backprop.** Provably equivalent in `beta -> 0` limit for symmetric weight matrices and convergent dynamics. Holomorphic EP gives exact BP gradient at *finite* `beta`.
4. **SoC fit.** Two-phase settling is repeated forward passes — NPU's strength. Local update means no full backward kernel. **In theory** this is the cleanest "forward-only training" candidate. **In practice**: convergence time of the settling dynamics is the rate-limiter and Hexagon NPU has no published cost model for the settling loop's iteration count.
5. **Falsifiers.**
   - No language model. If by end-2026 no EP-trained transformer of any size exists with competitive perplexity, the LM gate has failed for EP.
   - Settling-iteration count × forward cost must beat BP wall-clock on actual phones. Unmeasured.
   - Holomorphic EP requires holomorphic activation functions (complex-valued); standard transformer doesn't satisfy this without modification.
6. **2025-2026 progress.** Real and steady at CIFAR-10/ImageNet-32 scale; no LM, no phone deployment.

**Verdict: Tier 2. Most mathematically clean candidate for forward-only training. Worth one focused probe on Adreno/Hexagon with a small CRNN/ConvNet, but blocked from Tier 1 by lack of any LM-scale proof.**

### 3. Forward-Forward (FF)

1. **Math.** Each layer optimizes a local "goodness" objective `g(h) = sigma(||h||^2 - theta)`. Positive samples are real data, negative samples are generated/adversarial. Update per layer: `dW = dh g(h) - dh g(h_neg)`. No backward pass. No global error.
2. **Largest empirical scale.**
   - **Hinton, arXiv:2212.13345, 2022** — MNIST only (https://www.cs.toronto.edu/~hinton/FFA13.pdf).
   - **DeeperForward, ICLR 2025** — extends to 14-17 layer CNNs, CIFAR-10/100 (https://proceedings.iclr.cc/paper_files/paper/2025/file/7dd309df03d37643b96f5048b44da798-Paper-Conference.pdf).
   - **Self-Contrastive FF, *Nature Communications* 2025** (https://www.nature.com/articles/s41467-025-61037-0).
   - **FF for CNNs, *Scientific Reports* 2025** — MNIST, CIFAR-10, CIFAR-100 with "spatially-extended labels"; explicitly notes ImageNet does not work yet (https://www.nature.com/articles/s41598-025-26235-2).
   - **Contrastive FF for ViT, arXiv:2502.00571, 2025** — extends to vision transformers, accelerates convergence 5-20× over baseline FF but **still slower than BP with cross-entropy** (https://arxiv.org/html/2502.00571v2).
   - **Going Forward-Forward in Distributed Deep Learning, arXiv:2404.08573, 2024** — MNIST only, 4-layer MLP × 2000, claims 4× speedup over sequential FF; **no BP comparison** (https://arxiv.org/html/2404.08573v1).
   - **Replacing BP with FF for Transformer-shaped, hrcak srce paper 2024** — performance gap "minimal" vs BP but no LM at scale (https://hrcak.srce.hr/file/480463).
   - **No 1B-parameter language model has been trained by FF.**
3. **Equivalence to backprop.** No. FF optimizes a different objective (per-layer goodness, not global loss). It is *not* approximating BP.
4. **SoC fit.** *Best on paper*: NPU is forward-only by design. FF needs only forward passes. Positive and negative samples can be batched, NPU-friendly. CPU does the local-update arithmetic, which is small.
5. **Falsifiers.**
   - No LM. If by end-2026 no FF-trained LM ≥125M exists with competitive perplexity, FF's LM gate has failed.
   - "Negative sample generation" is the fundamental gap — Hinton's MNIST trick doesn't extend to natural images or text.
   - The 2025 Sci. Reports paper acknowledges this: "Hinton's negative example generation approach works well for MNIST but does not easily extend to CIFAR-10, ImageNet and STL-10."
6. **2025-2026 progress.** Active community, ~5-10 papers/year, but none has crossed the LM threshold.

**Verdict: Tier 3. The strongest SoC fit on paper of any biologically-inspired family, but no LM-scale evidence and the negative-sample problem is unsolved at scale. Re-evaluate annually.**

### 4. Energy-Based Models / Modern Hopfield

1. **Math.** Define energy `E_theta(x)`. Density `p(x) ∝ exp(-E(x))`. Training: minimize `KL(p_data || p_model)` via contrastive divergence (CD-k), persistent CD, score matching, NCE, or Langevin-MCMC. Update: `dtheta = E_data[dE/dtheta] - E_model[dE/dtheta]`. Modern Hopfield: continuous energy `E(x) = -log-sum-exp(beta X x) + ...` is **mathematically equivalent to one softmax-attention head** (Ramsauer et al. 2020).
2. **Largest empirical scale.**
   - **Improved CD Training of EBMs, Du et al., ICML 2021** — image generation up to ImageNet-128; not LM (https://energy-based-model.github.io/improved-contrastive-divergence/).
   - **Stochastic Attention via Langevin on Modern Hopfield Energy, arXiv:2603.06875, 2026** (https://arxiv.org/html/2603.06875).
   - **Modern Hopfield Networks with Continuous-Time Memories, arXiv:2502.10122, 2025** (https://arxiv.org/html/2502.10122v1).
   - **HEN — Hopfield Encoding Networks, arXiv:2409.16408, 2024** (https://arxiv.org/abs/2409.16408).
   - **No EBM-trained language model at LLM scale.** EBM training (CD/Langevin) is at small-image-generation scale.
3. **Equivalence to backprop.** EBM training **does use backprop** to update `theta`; the difference is the loss (`E_data - E_model`) and the need for MCMC samples. So EBM is *not* a backprop-replacement; it is a different *objective*.
4. **SoC fit.** Langevin/MCMC sampling = many forward passes per update — NPU-friendly *if* MCMC chains are short. But MCMC mixing is the rate-limiter and a known scaling pain point.
5. **Falsifiers.**
   - No EBM-trained LM. If LeCun's EBM-LLM (JEPA-style world-model-as-LM) does not produce a ≥1B EBM-trained LM by end-2026, the LM gate has failed.
   - MCMC mixing time per update on text is unmeasured at scale.
6. **2025-2026 progress.** Active in image/generative side, mostly inactive in LM. Modern Hopfield = attention is an *architectural* result, not a training-method result.

**Verdict: Tier 3 as a training paradigm. Modern Hopfield's attention equivalence is interesting as an architectural framing, not a training-rule replacement.**

### 5. Resonance-based / Oscillator-based learning (operator-mentioned)

This is the most important section because the operator specifically named "resonance-based." Honest answer below.

1. **Math.** Highly heterogeneous. Three sub-families:
   - **Adaptive Resonance Theory (ART, Carpenter & Grossberg 1976-)**: incremental match-based learning. Vigilance parameter `rho` controls category resolution. Vigilance-driven plasticity. *Not a deep-learning update rule.*
   - **Coupled oscillator / oscillator network computing**: networks of nonlinear oscillators (Hopf, Kuramoto, Stuart-Landau). Compute via phase-locking and synchronization. Trained either by Hebbian rules or by backprop-through-time on the oscillator dynamics.
   - **Stochastic resonance neural networks**: noise as a computational resource; sigmoidal nodes replaced by stochastic-resonance nodes (https://www.nature.com/articles/s44172-024-00314-0).
2. **Largest empirical scale.**
   - **Deep Oscillatory Neural Network (DONN), Pal et al., *Scientific Reports* 2025** — complex-valued Hopf oscillators trained by *complex backprop*. Best result: 85.2% IMDB sentiment. **No LM.** Acknowledges quadratic hardware scaling problem (https://www.nature.com/articles/s41598-025-24837-4 ; https://arxiv.org/abs/2405.03725).
   - **Harmonic Oscillator Recurrent Networks (HORN)**, PNAS 2025 — outperforms non-oscillatory RNNs on small tasks (https://www.pnas.org/doi/10.1073/pnas.2412830122).
   - **Computing with Oscillators review, *npj Unconventional Computing* 2024** — combinatorial optimization and pattern retrieval, *not LM* (https://www.nature.com/articles/s44335-024-00015-z).
   - **Coupled-oscillator Ising chips, *Nature Electronics* 2025 (Communications Engineering 2024)** — combinatorial optimization (Ising solvers), not deep learning training (https://www.nature.com/articles/s41928-025-01393-3 ; https://www.nature.com/articles/s44172-024-00261-w).
   - **ART + LLM "MemoryART" 2024** — ART used as an *external memory layer* for an LLM, not as the LLM training algorithm.
   - **No LM trained by an oscillator-based or resonance-based learning rule exists.** "Resonance-based learning" as a deep-learning paradigm with scale receipts does not currently exist.
3. **Equivalence to backprop.** DONN is trained by complex-valued BP. ART is a different paradigm (match-based incremental, not gradient-based at all). Oscillator BPTT *is* backprop.
4. **SoC fit.** Snapdragon SM8750 has **no oscillator fabric** — no Kuramoto, Hopf, or Ising hardware. Coupled-oscillator Ising machines (https://www.nature.com/articles/s41928-025-01393-3) are 65 nm CMOS chips with custom oscillator arrays; you cannot run them on Hexagon NPU. Simulating oscillator dynamics on a digital NPU costs more than running ordinary backprop on the same NPU. **The "physically natural" SoC argument for resonance-based learning fails because the SoC has no resonance primitive.**
5. **Falsifiers.**
   - **Hard falsifier #1**: No oscillator-based system has trained an LM at ≥125M parameters. Negative, conclusive.
   - **Hard falsifier #2**: SM8750 has no oscillator/Ising primitive. Digital simulation of oscillator dynamics is strictly more expensive than the equivalent transformer forward pass on the same NPU.
   - **Hard falsifier #3**: The "operator's intuition" that resonance is natural for the SoC misidentifies the physical substrate — phones are deterministic digital substrates with active cooling. Resonance is a meaningful primitive on analog/neuromorphic/optical substrates, not Snapdragon-class SoCs.
6. **2025-2026 progress.** Active in neuromorphic / Ising / oscillator-fabric communities. None on commodity phone SoCs. **No LM**.

**Verdict (Resonance specifically): Tier 3. The operator's intuition that "resonance is natural for the SoC" is wrong as a hardware fit — SM8750 is a digital NPU/GPU/CPU substrate without oscillator primitives. Resonance-based learning is real and interesting on dedicated oscillator/Ising hardware (Maxim Igolkin coupled-oscillator chip, Toshiba SBM, MIT Lincoln Lab Ising machine), but it is *not* a credible LM training paradigm and it has *zero SoC fit on this phone*.** If the operator wants to pursue this, the right move is a future RunPod or partner-lab Ising-fabric experiment, not a phone experiment. The biggest risk in this section is `fp-demogravity`: simulating oscillators on the NPU is a demo, not a system.

### 6. Free-Energy Principle / Active Inference (Friston)

1. **Math.** Agent minimizes variational free energy `F[q, p] = E_q[log q(s) - log p(s, o)]`. In deep nets, this *reduces to predictive coding* (Friston 2010, Bogacz 2017). Active inference adds: action is selected to minimize *expected* free energy. Reframings: Da Costa et al. arXiv:2402.14460, 2024 (https://arxiv.org/pdf/2402.14460).
2. **Largest empirical scale.**
   - FEP/active-inference papers as *agentic frameworks* (Davis, RobotXR) exist but **do not change the weight update rule from BP/PC**.
   - **In vitro neural validation, *Nature Communications* 2023** — supports FEP in biological networks, not artificial scale (https://www.nature.com/articles/s41467-023-40141-z).
   - Friston (Davos 2024) publicly attacked deep learning as lacking "calculus of beliefs" (https://medium.com/aimonks/deep-learning-is-rubbish-karl-friston-yann-lecun-face-off-at-davos-2024-world-economic-forum-494e82089d22). Rhetoric, not algorithmic LM result.
3. **Equivalence to backprop.** FEP-as-loss for deep networks = predictive coding ≈ BP under fixed-prediction assumption. As a *training rule for weights*, FEP is not different from PC.
4. **SoC fit.** Same as PC. FEP-as-control-loss adds an expected-free-energy planner — that's an inference-time/control-time module, not a training algorithm.
5. **Falsifiers.**
   - No LM weight-trained by FEP-as-loss that differs from PC.
   - If "FEP-LLM" claims are made without a different weight-update rule, they reduce to BP-with-a-different-loss and the gate is just "does it improve held-out perplexity?"
6. **2025-2026 progress.** Active in agentic AI rhetoric, no algorithmic LM training result.

**Verdict: Tier 3. As a *training paradigm*, FEP collapses to PC. As an *agent framework*, it is an inference/control layer on top of an underlying network — useful for the agentic faculty, irrelevant for the weight-update question.**

### 7. Local Hebbian / SoftHebb / three-factor plasticity

1. **Math.** Classical Hebbian: `dW = eta x y^T`. STDP: weight change depends on relative pre/post spike timing. SoftHebb (Journé et al. 2022): soft winner-take-all + Hebbian `dW`, no error signal. Three-factor: `dW = eta f(pre, post) g(global modulator)` where `g` is reward / TD-error / dopamine-analog.
2. **Largest empirical scale.**
   - **SoftHebb, Journé et al., ICLR 2023, arXiv:2209.11883**: 99.4% MNIST, 80.3% CIFAR-10, 76.2% STL-10, **27.3% ImageNet** with 5 hidden layers + linear classifier (https://arxiv.org/abs/2209.11883). The 27.3% ImageNet is the largest empirical scale for any Hebbian-only deep network without error feedback.
   - **FastHebb 2024, *Neurocomputing*** — first ImageNet-scale Hebbian (https://www.sciencedirect.com/science/article/pii/S0925231224006386).
   - **Three-factor in SNNs review 2025** — applications in spiking control/classification, not LM (https://www.sciencedirect.com/science/article/pii/S2666389925002624).
   - **Dendritic Localized Learning, Liu et al., ICML 2025** — MLPs/CNNs/RNNs only, "state of the art among bio-plausible" (https://arxiv.org/abs/2501.09976).
   - **No language model trained by Hebbian rules.**
3. **Equivalence to backprop.** No. Hebbian is a different (unsupervised, feature-learning) objective. Three-factor adds a reward signal but is still a local rule, not BP.
4. **SoC fit.** Hebbian is **strictly local** — no global error signal flows. Each layer's weight update can run on whichever device hosts that layer, with no synchronization. CPU only orchestrates. This is the cleanest "no global gradient flow" architecture for heterogeneous SoCs.
5. **Falsifiers.**
   - No LM. Hebbian feature-learning on language has not been demonstrated.
   - ImageNet 27% top-1 is well below SOTA (~85%+). Hebbian is a *feature learner*, not a finished classifier — needs a supervised head.
6. **2025-2026 progress.** Steady (FastHebb, SoftHebb, Dendritic Localized Learning), no LM crossover.

**Verdict: Tier 2 as a feature-learning probe (unsupervised pre-training of frozen-trunk features). Tier 3 as a primary training rule for LM.**

### 8. Information Bottleneck / MDL

1. **Math.** IB: maximize `I(T; Y) - beta I(T; X)` where `T` is the representation. Implementations: VIB (Alemi et al. 2017), Deep Variational IB. HSIC Bottleneck (Ma et al. 2019) replaces MI with Hilbert-Schmidt independence.
2. **Largest empirical scale.**
   - **HSIC Bottleneck, arXiv:1908.01580** — "deep learning without backprop" claim, small networks only (https://arxiv.org/abs/1908.01580).
   - **IB Analysis via Lossy Compression, ICLR 2024** — analysis tool, not training rule (https://openreview.net/forum?id=huGECz8dPp).
   - **Generalized IB Theory, arXiv:2509.26327, 2025** (https://arxiv.org/abs/2509.26327).
   - **No IB-trained LM at LLM scale.** IB is mostly an *analysis lens* on what backprop-trained networks do, plus a regularizer term added to BP loss.
3. **Equivalence to backprop.** IB is a *loss / objective*, optimized by BP. HSIC-bottleneck variant claims to avoid BP but is small-scale only.
4. **SoC fit.** As a regularizer, none — it just modifies the loss. As HSIC-bottleneck local rule, similar to Hebbian per-layer fit.
5. **Falsifiers.**
   - No LM trained by IB-only (no BP) objective.
6. **2025-2026 progress.** Active in *theory* of deep learning, not in *replacing* training.

**Verdict: Not applicable as a primary training rule. IB is an analysis lens or a regularizer.**

### 9. Pipeline-parallel SGD with bubble-free schedules

1. **Math.** Standard backprop pipelined across stages. **Zero-Bubble (ZB)** key insight: split backward into `B_input` (gradient w.r.t. input) and `B_param` (gradient w.r.t. parameters); `B_param` can be deferred and scheduled into bubbles. **ZB-V**, **1F1B-V**, **AdaPtis** handle heterogeneous stage costs.
2. **Largest empirical scale.**
   - **ZB Pipeline Parallelism, ICLR 2024 (Qi et al., arXiv:2401.10241)** — 23% throughput vs 1F1B at same memory; 31% with relaxed memory (https://arxiv.org/abs/2401.10241).
   - **AdaPtis, arXiv:2509.23722, 2025** — heterogeneous pipelines (https://arxiv.org/pdf/2509.23722).
   - **Seq1F1B, NAACL 2025** — sequence-level pipelining (https://aclanthology.org/2025.naacl-long.454.pdf).
   - **PipeFill, 2024** — uses GPU bubbles for auxiliary work (https://www.pdl.cmu.edu/PDL-FTP/BigLearning/Pipefill-2410.07192v1.pdf).
   - **Largest published**: GPT-class LMs trained with ZB-like schedules across thousands of GPUs.
3. **Equivalence to backprop.** **Identical**. Pipeline parallelism is BP rearranged in time, not a different rule.
4. **SoC fit.** **Perfect.** CPU control plane = pipeline orchestrator; GPU = flexible compute stage; NPU = frozen-or-light-update forward stage; UFS storage = weight reservoir. Three-device pipeline on one phone is a direct read of the SoC.
5. **Falsifiers.**
   - **Hard #1**: bubble cost saved must exceed cross-device transfer overhead on phones. Phone PCIe doesn't exist; everything is unified memory, but cache flushes / repacks may eat the saving.
   - **Hard #2**: NPU graph mutation cost — switching microbatches may force QNN recompile.
   - **Hard #3**: thermal — if pipelining pegs all three devices simultaneously, the phone throttles faster than the bubble cost.
6. **2025-2026 progress.** Active and pushing into hetero/elastic-bubble territory.

**Verdict: Tier 1. Highest-confidence next-step experimental investment. This is the answer to the "natural fit" question that survives Resistance V2.**

### 10. Synthetic Gradients / Decoupled Neural Interfaces

1. **Math.** Each module `M_i` has a synthetic-gradient predictor `G_i`. Forward: `z_i = M_i(z_{i-1})`. Synthetic update: `dtheta_i = G_i(z_i, optional_context)` *without* waiting for global backward. `G_i` itself is trained from true gradients when they later arrive.
2. **Largest empirical scale.**
   - **Jaderberg et al., DeepMind 2016, arXiv:1608.05343** — RNN/CNN on language modeling and image classification; **3× wall-clock speedup** for asynchronous training (https://arxiv.org/abs/1608.05343).
   - **Understanding Synthetic Gradients, arXiv:1703.00522, 2017** (https://arxiv.org/abs/1703.00522).
   - **Benchmarking DNI, arXiv:1712.08314, 2017** (https://arxiv.org/abs/1712.08314).
   - **No 2024-2025 LM-scale DNI revival.** The line went quiet around 2018 because gradient predictors drift on large models.
3. **Equivalence to backprop.** Surrogate. Approximates BP when `G_i` is well-calibrated; drifts otherwise.
4. **SoC fit.** Decouples module updates — CPU/GPU/NPU can run different modules out of sync. Reduces synchronization overhead.
5. **Falsifiers.**
   - **Hard**: gradient-predictor drift at LM scale. Why the line died.
   - Memory cost of storing `G_i` per module.
6. **2025-2026 progress.** Minimal. The community moved to pipeline-parallel BP instead.

**Verdict: Tier 3. Historically interesting; the pipeline-parallel community absorbed the use case (CPU/GPU async updates) without the drift cost.**

### 11. Reservoir Computing / Echo State Networks

1. **Math.** Fixed random recurrent reservoir `h_t = tanh(W_in x_t + W h_{t-1})`, `W` *frozen at initialization*. Only a linear readout `y_t = W_out h_t` is trained, usually by ridge regression or simple SGD.
2. **Largest empirical scale.**
   - **Reservoir Computing as a Language Model, arXiv:2507.15779, 2025** — character-level Shakespeare, no LM-scale evaluation. Authors call for "scaling laws for RC" as open work (https://arxiv.org/abs/2507.15779).
   - **Syntactic Learnability of ESN at Scale, arXiv:2503.01724, 2025** — ESN with large hidden state matches Transformer on **grammaticality judgment at ~100M words**. Not generation, not perplexity-competitive at LM scale (https://arxiv.org/html/2503.01724v1).
   - **Locally Connected ESN, ICLR 2025** — scales hidden state size (https://openreview.net/forum?id=KeRwLLwZaw).
3. **Equivalence to backprop.** No. RC trains only the readout — much weaker than BP.
4. **SoC fit.** **Strong** — frozen reservoir = pure inference (NPU); readout = small linear regression (CPU). Almost zero "training" overhead.
5. **Falsifiers.**
   - LM perplexity gap to transformer at any scale > 100M tokens is large.
   - No autoregressive generation results competitive with small transformers.
6. **2025-2026 progress.** Steady, narrow.

**Verdict: Tier 3. Cheap to try as a SoC microbench, but the representational ceiling is too low for primary Polymath training.**

### 12. Zeroth-order / forward-only

1. **Math.** SPSA (Spall 1992). Sample perturbation `u ~ N(0, I)`. Estimate gradient as `g = ((f(theta + eps u) - f(theta - eps u)) / (2 eps)) u`. Average over `K` perturbations to reduce variance. Update `theta -= eta g`.
2. **Largest empirical scale.**
   - **MeZO, Malladi et al., NeurIPS 2023** — fine-tuned OPT-30B/66B with one A100; comparable to first-order in some tasks (https://proceedings.neurips.cc/paper_files/paper/2023/file/a627810151be4d13f907ac898ff7e948-Paper-Conference.pdf).
   - **MobiZO, EMNLP 2025 (Yu et al., arXiv:2409.15520)** — **fine-tuned Llama-2-7B and TinyLlama-1.1B on OnePlus 12 Hexagon NPU**: 5.76 s/step at seq=128 batch=16 on TinyLlama-1.1B; 2.11-3.98 GB memory; Llama-2-7B 12.61-14.53 GB memory. Up to 8.1% accuracy improvement over LoRA-FA baseline (https://arxiv.org/html/2409.15520v3).
   - **ZeroQAT, arXiv:2509.00031, 2025** — forward-only QAT, **6.7B on OnePlus 12** (https://arxiv.org/abs/2509.00031).
   - **AGZO (Activation-Guided ZO), arXiv:2601.17261, 2026** — outperforms MeZO/LOZO (https://arxiv.org/html/2601.17261v3).
   - **Sparse MeZO, arXiv:2402.15751, 2024** (https://arxiv.org/html/2402.15751).
   - **MaZO, EMNLP 2025** — masked multi-task ZO (https://arxiv.org/html/2502.11513v1).
   - **ZeroFTL, arXiv:2511.11362, 2025** — backprop-free on-device fine-tuning (https://arxiv.org/html/2511.11362).
   - **Learning a ZO Optimizer, arXiv:2510.00419, 2025** (https://arxiv.org/html/2510.00419v1).
3. **Equivalence to backprop.** Surrogate. `K` perturbations give a finite-sample estimate of the gradient. Variance ~ O(d/K) where d = parameter count, so naive ZO is very slow at LLM scale. MeZO and successors exploit low-rank structure to reduce effective d.
4. **SoC fit.** **Direct hit.** NPU does only forward passes. ZO is forward-only by construction. No backward kernel, no autograd graph, no activation storage. CPU does the small post-perturbation update.
5. **Falsifiers.**
   - Forward-query count per useful update vs FO: ZO needs 2K forwards per step; first-order needs 1 forward + 1 backward. If NPU forward isn't > 2× cheaper than (forward + backward) on this SoC, ZO loses on wall-clock.
   - Thermal: 2K consecutive forwards may throttle faster than a forward+backward.
   - Quality ceiling: ZO has noisier updates; longer to convergence on hard tasks.
6. **2025-2026 progress.** Most active alternative-credit-assignment line by paper count. Real numbers on actual Snapdragon phones.

**Verdict: Tier 1. Most empirically grounded "different update rule" for phones. Already measured on Hexagon NPU.**

### 13. Spiking / Neuromorphic

1. **Math.** Discrete-time spikes; surrogate gradient training (BPTT through non-differentiable spike) for SNNs. Or rate-coded approximation (SpikeLLM, SpikingBrain).
2. **Largest empirical scale.**
   - **SpikeGPT, arXiv:2302.13939, 2023** — small GPT with binary spikes, 22× fewer SynOps (https://arxiv.org/abs/2302.13939).
   - **SpikeLLM, ICLR 2025, arXiv:2407.04752** — 7-70B LLMs with bio-plausible spiking; -25.51% WikiText2 PPL and +3.08% zero-shot on LLAMA2-7B 4A4W (https://arxiv.org/abs/2407.04752).
   - **SpikingBrain, arXiv:2509.05276, 2025** — 7B and 76B brain-inspired LLMs. **Trained on MetaX (Chinese non-NVIDIA) GPU cluster**, not phones. 76B is a hybrid-linear MoE. 69.15% spike sparsity. "Continual pre-training" from Qwen2.5-7B base, only 150B tokens. Claim: 100× speedup in Time-to-First-Token for 4M-token sequences. **This is the only "biologically inspired" LM at LLM scale, but the training algorithm is still essentially BP on a reshaped Qwen architecture, not a new credit-assignment rule** (https://arxiv.org/abs/2509.05276).
3. **Equivalence to backprop.** Surrogate-gradient SNN training uses BP. SpikingBrain is BP. So "spiking" is an *architectural* choice (sparsity + binary activations + linear attention), not a *training-rule* replacement.
4. **SoC fit.** **SM8750 has no spiking accelerator.** Hexagon NPU is INT4/INT8/FP16 dense compute. Running an SNN on Hexagon would simulate spikes as binary tensors — the sparsity advantage is mostly lost on dense matmul. Spikes are physically natural on Loihi, SpiNNaker, Akida — not Snapdragon.
5. **Falsifiers.**
   - SM8750 has no native spike primitive.
   - Spike sparsity on a dense NPU is software-only, doesn't reduce real energy.
6. **2025-2026 progress.** Active; the SpikingBrain-76B result is real but does not translate to phone training.

**Verdict: Tier 3 for this SoC. SpikingBrain's *architectural* lessons (linear attention + structured sparsity) are worth porting; the *spiking* part has no SoC primitive to land on.**

---

## What about "resonance-based" specifically?

The operator named "resonance-based" as a candidate to investigate. Honest answer:

- **There is no "resonance-based learning" family with LLM-scale evidence as of 2026-05-16.**
- The most concrete recent work is **Deep Oscillatory Neural Networks (Pal et al., *Sci. Reports* 2025)** which trains complex-valued Hopf oscillators using **complex-valued backprop**, peaking at 85.2% IMDB sentiment classification. It is not an alternative to backprop — it uses backprop.
- **Coupled-oscillator Ising machines** (Lo et al., *Nature Electronics* 2025; *Communications Engineering* 2024) are real and physically interesting, but they are *custom 65 nm CMOS chips with oscillator arrays* solving combinatorial optimization, not neural network training. They have no analog on Snapdragon SM8750.
- **Adaptive Resonance Theory (ART)** is a different paradigm (match-based incremental classification with vigilance) and has not been scaled to LMs. The "MemoryART" line (2024) uses ART as an *external memory layer* for an existing LLM, not as a training rule.
- **Stochastic resonance** in NNs (Andreev et al., *Comms. Eng.* 2024) is a node nonlinearity choice, not a learning paradigm. Standard backprop trains it.
- The *intuition* that "resonance is natural for the SoC" is **wrong on this substrate**: Snapdragon is a deterministic digital substrate. Resonance is a meaningful primitive on analog/oscillator/optical/Ising fabrics. Simulating oscillator dynamics on Hexagon NPU is *strictly more expensive* than running ordinary transformer forward passes on the same NPU, because the oscillator simulation is itself a series of dense matrix operations plus extra integration overhead.

**Recommendation on resonance:** archive as a *Tier-3 future bet for partner-lab oscillator-fabric hardware* (e.g., RunPod doesn't help; this needs Intel Loihi, Akida, BrainScaleS, or a custom oscillator chip). Do not spend Polymath SM8750 engineer-weeks simulating oscillators on Hexagon. That would be `fp-demogravity` and `fp-toolbusy` (forbidden patterns from Resistance V2).

If the operator wants the *intuition* of "letting the substrate's natural physics do the work" preserved, the on-SoC version of that intuition is **not oscillator simulation** — it is **(a) NPU forward as the natural "settling" of a quantized linear computation, (b) GPU as the natural flexible substrate for non-quantization-friendly ops, and (c) ZO/forward-only methods that respect the NPU's actual physical asymmetry (forward is cheap, backward is hostile).** That intuition lands the operator on **Tier-1: ZB pipeline-parallel BP + ZO surrogate** — which is what the rest of this document concludes.

---

## Concrete experiments to test the top 2 candidates on SM8750

Both experiments use the existing Polymath baselines (dense Qwen3-4B / Gemma 4 E2B) so they don't fall into `fp-demogravity`.

### Experiment A — Heterogeneous Pipeline-Parallel Backprop (Tier-1 candidate #1)

- **Model.** Qwen3-4B base, BF16, 28-layer decoder. Split into 4 microstages:
  - Stage 0 (embedding + first 7 layers) → NPU forward only, frozen
  - Stage 1 (next 7 layers) → GPU forward + backward, trainable LoRA
  - Stage 2 (next 7 layers) → GPU forward + backward, trainable LoRA
  - Stage 3 (last 7 layers + head) → CPU forward + backward, trainable LoRA + LN
- **Dataset.** 200M tokens from a held-out Polymath corpus (deduped, replay-protected).
- **Schedule.** ZB-1F1B-V variant with `B_input/B_param` split. Microbatch size 4. Pipeline microbatch count 8.
- **Authority metric.** Examples/sec to held-out validation loss target X, energy proxy via battery drain rate under fan + bypass charging, peak PSS, thermal stability over 60-min sustained run.
- **Comparison.** Baseline = single-GPU LoRA on Adreno only (no pipeline).
- **Gate.** Pipeline schedule must beat single-GPU baseline by ≥20% on examples/sec to target validation loss, with no quality regression, no LMK pressure, and stable thermal state.
- **Falsifier.** If cross-device transfers (NPU→GPU→CPU) burn >30% of cycle time or QNN graph mutation forces recompile per microbatch, the heterogeneous schedule is unsafe — fall back to ZB on GPU alone with NPU frozen as inference-only.
- **Engineering cost.** ~3 engineer-weeks (existing ZB code + adapter layer for QNN-bound stage).

### Experiment B — ZO + MeBP Combined Pipeline (Tier-1 candidate #2)

- **Model.** Qwen3-4B base, Q4 deployed.
- **Method.** Three trainable surfaces in parallel:
  - **NPU**: 12 frozen layers, used as forward feature extractor.
  - **GPU**: 8 trainable layers with MeBP (rematerialized backprop), LoRA rank 16.
  - **CPU**: head + LN + 2 small adapters trained by **MobiZO/MeZO** (forward-only ZO).
- **Schedule.** Asynchronous: GPU does MeBP step, CPU does ZO step in parallel; NPU sustains forward stream.
- **Dataset.** Same 200M-token Polymath corpus.
- **Authority metric.** Examples/sec to held-out validation loss; energy/joule; thermal sustained over 90 min.
- **Comparison.** Baselines: (1) LoRA-FA single-GPU (Adreno); (2) MobiZO single-NPU.
- **Gate.** Combined parallel system must beat better of (1) or (2) by ≥30% on examples/sec to target loss, with no regression, sustained thermals.
- **Falsifier.** If ZO's forward-query count is so high that NPU saturation kills the GPU MeBP step's effective throughput, or if MeBP rematerialization on GPU evicts the LoRA weights from cache, the two methods don't co-exist productively.
- **Engineering cost.** ~5 engineer-weeks (MobiZO + MeBP integration is non-trivial).

These two experiments are the *only* "natural-fit" experiments worth running on SM8750 in 2026 Q3 under Resistance V2. Everything else in the 13-paradigm catalog fails the LM-scale gate.

---

## Speculative tier vs research-viable tier

**First-wave (research-viable now):**
- Pipeline-parallel BP with bubble-aware scheduling (#9)
- MeBP / first-order memory-rematerialized BP (Polymath blind-spots list #1)
- MobiZO / MeZO / ZeroQAT / AGZO and the ZO family (#12)
- Quantization-aware on-device training (blind-spots #10)

**Second-wave (research-viable as small probes; do not commit primary phone-weeks):**
- Holomorphic Equilibrium Propagation (#2) — strongest math, no LM
- μPC / Predictive Coding (#1) — promising depth scaling, no transformer
- SoftHebb / Hebbian-no-feedback (#7) — feature-learning probe for the frozen trunk

**Speculative (do not fund without partner hardware or LM-scale breakthrough):**
- Forward-Forward (#3) — best NPU fit on paper, no LM proof, negative-sample problem unsolved
- Modern Hopfield / EBM (#4) — Modern-Hopfield-as-attention is architectural, not training-rule
- Resonance / Oscillator (#5) — no SoC primitive, no LM
- Free Energy Principle (#6) — collapses to PC as training rule
- Adaptive Resonance Theory — not a deep-learning training rule
- Reservoir Computing (#11) — representational ceiling too low for primary LM
- Synthetic Gradients / DNI (#10) — community moved on; drift at LM scale
- Spiking / SpikingBrain (#13) — SoC has no spike primitive; sparsity story is software-only on dense NPU

**Not applicable as a primary training rule:**
- Information Bottleneck / MDL (#8) — analysis lens / regularizer, not a different weight-update rule

---

## Information-geometric framing (gradient-information per joule)

A rough sketch — formal energy measurements pending. For one optimizer step on a B-parameter LM:

| Method | Forward passes | Backward kernel | Activation storage | Gradient bits used per step |
|---|---|---|---|---|
| Backprop (FO) | 1 | full | full | O(B) (dense gradient) |
| MeBP (rematerialized BP) | 2 | full | partial | O(B) |
| Pipeline BP (ZB-V) | 1 | full, split | per-stage | O(B), staggered |
| MeZO (ZO with K=1 perturbation) | 2 | none | none | O(B) but variance ~O(B) → noisy |
| AGZO (activation-guided ZO) | 2 | none | none | O(B), variance reduced |
| Forward-Forward | 2 | none | none | O(B_local) per layer, no global |
| Equilibrium Propagation (settled) | T+T | none | per layer | O(B), exact in limit |
| Predictive Coding (settled) | T iterations | none | per layer | O(B), exact in fixed-pred limit |

Read: ZO trades activation memory and backward kernel for **2K** forward passes per step. On Hexagon NPU (forward-strong), 2K forwards may cost < (1 forward + 1 backward + optimizer) of GPU/CPU backward. The crossover depends on K, model size, and the NPU/GPU throughput ratio. **This is the empirical question Experiment B answers, and it is the strongest information-geometric argument for ZO on this SoC.**

For EP/PC, T (settling iterations) plays the role of K. Hexagon-friendly if T < ~20. No measured value at LM scale.

---

## Hard falsifiers (for the verdict)

The verdict is **falsified** if any of these become true in 2026:

1. **A research group trains a 1B+ LM with predictive coding, equilibrium propagation, or forward-forward to competitive perplexity vs a backprop baseline.** Currently zero such results.
2. **MeBP or MobiZO loses to Adreno-only LoRA on examples/sec-to-target-quality in our actual SM8750 measurement.** Currently MobiZO measured at 5.76 s/step on OnePlus 12; needs SM8750 confirmation.
3. **ZB-pipeline schedule on SM8750 fails to beat single-GPU baseline.** Reasons: cross-device transfer cost, NPU graph mutation cost, thermal stacking.
4. **An oscillator-fabric or Ising chip becomes available for Polymath partnership.** Then the "resonance" question reopens with real hardware fit. Until then, it stays Tier-3.
5. **Friston / DeepMind / Verses publish an LM trained by FEP or PC at competitive perplexity.** Would force a Tier-2 → Tier-1 promotion.
6. **SpikingBrain or successor lands on Hexagon NPU with measured energy advantage over Qwen2.5-7B on SM8750.** Would force spiking into Tier-2.

---

## Sources (primary)

### Predictive Coding
- Whittington & Bogacz 2017 (relationship to BP): https://pmc.ncbi.nlm.nih.gov/articles/PMC8970408/ ; https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0266102
- Predictive Coding as a Neuromorphic Alternative to Backpropagation, *Neural Computation* 2023: https://direct.mit.edu/neco/article/35/12/1881/117833/
- μPC Innocenti et al. NeurIPS 2025 (arXiv:2505.13124): https://arxiv.org/abs/2505.13124 ; https://arxiv.org/html/2505.13124v1
- Predictive Coding Can Do Exact BP (Salvatori et al. 2021): https://arxiv.org/abs/2103.03725
- VERSES benchmarking PCNs: https://www.verses.ai/research-blog/benchmarking-predictive-coding-networks-made-simple
- Predictive coding and BP review: https://arxiv.org/pdf/2304.02658

### Equilibrium Propagation
- Holomorphic EP, Laborieux & Zenke 2022 (arXiv:2209.00530): https://arxiv.org/abs/2209.00530
- Scaling EP to Deeper Networks 2025 (arXiv:2509.26003): https://arxiv.org/html/2509.26003v1
- Scalable EP via Intermediate Error Signals 2025 (arXiv:2508.15989): https://arxiv.org/html/2508.15989v1
- Directed EP Revisited, Mathematics 2025: https://www.mdpi.com/2227-7390/13/11/1866
- Improving EP without Equilibrium ICLR 2024: https://proceedings.iclr.cc/paper_files/paper/2024/file/6a55f024db3f771194bdadc8f3a35381-Paper-Conference.pdf
- Scaling EP to Deep ConvNets, *Frontiers* 2021: https://pmc.ncbi.nlm.nih.gov/articles/PMC7930909/

### Forward-Forward
- Hinton 2022 (arXiv:2212.13345): https://www.cs.toronto.edu/~hinton/FFA13.pdf
- DeeperForward ICLR 2025: https://proceedings.iclr.cc/paper_files/paper/2025/file/7dd309df03d37643b96f5048b44da798-Paper-Conference.pdf
- Self-Contrastive FF, *Nature Communications* 2025: https://www.nature.com/articles/s41467-025-61037-0
- FF for CNNs, *Sci. Reports* 2025: https://www.nature.com/articles/s41598-025-26235-2
- Contrastive FF for ViT 2025 (arXiv:2502.00571): https://arxiv.org/html/2502.00571v2
- Going Forward-Forward in Distributed DL 2024 (arXiv:2404.08573): https://arxiv.org/html/2404.08573v1
- On Advancements of FF 2025 (arXiv:2504.21662): https://arxiv.org/html/2504.21662v1

### Energy-Based / Modern Hopfield
- Modern Hopfield = Attention, Ramsauer et al. 2020 NeurIPS: https://arxiv.org/abs/2008.02217
- Improved CD Training of EBMs ICML 2021: https://energy-based-model.github.io/improved-contrastive-divergence/
- Stochastic Attention via Langevin on Modern Hopfield Energy 2026 (arXiv:2603.06875): https://arxiv.org/html/2603.06875
- Modern Hopfield with Continuous-Time Memories 2025 (arXiv:2502.10122): https://arxiv.org/html/2502.10122v1
- HEN — Hopfield Encoding Networks 2024 (arXiv:2409.16408): https://arxiv.org/abs/2409.16408

### Resonance / Oscillator / ART
- Deep Oscillatory Neural Network, *Sci. Reports* 2025 (arXiv:2405.03725): https://www.nature.com/articles/s41598-025-24837-4
- HORN, *PNAS* 2025: https://www.pnas.org/doi/10.1073/pnas.2412830122
- Computing with Oscillators review, *npj Unconventional Computing* 2024: https://www.nature.com/articles/s44335-024-00015-z
- Coupled-oscillator Ising chip, *Nature Electronics* 2025: https://www.nature.com/articles/s41928-025-01393-3
- Robust NNs using stochastic resonance, *Comms. Eng.* 2024: https://www.nature.com/articles/s44172-024-00314-0
- Adaptive Resonance Theory, Grossberg 2024 article: https://www.frontiersin.org/journals/systems-neuroscience/articles/10.3389/fnsys.2025.1630151/full

### Free Energy / Active Inference
- Reframing the Expected Free Energy 2024 (arXiv:2402.14460): https://arxiv.org/pdf/2402.14460
- Experimental validation of FEP with in vitro neural networks, *Nature Communications* 2023: https://www.nature.com/articles/s41467-023-40141-z
- Friston-LeCun Davos 2024: https://medium.com/aimonks/deep-learning-is-rubbish-karl-friston-yann-lecun-face-off-at-davos-2024-world-economic-forum-494e82089d22

### Local Hebbian / Three-factor
- SoftHebb, Journé et al. ICLR 2023 (arXiv:2209.11883): https://arxiv.org/abs/2209.11883
- FastHebb, *Neurocomputing* 2024: https://www.sciencedirect.com/science/article/pii/S0925231224006386
- Three-factor in SNNs review 2025: https://www.sciencedirect.com/science/article/pii/S2666389925002624
- Dendritic Localized Learning ICML 2025 (arXiv:2501.09976): https://arxiv.org/abs/2501.09976

### Information Bottleneck
- HSIC Bottleneck (arXiv:1908.01580): https://arxiv.org/abs/1908.01580
- IB Analysis via Lossy Compression ICLR 2024: https://openreview.net/forum?id=huGECz8dPp
- Generalized IB Theory 2025 (arXiv:2509.26327): https://arxiv.org/abs/2509.26327

### Pipeline-Parallel
- Zero Bubble Pipeline Parallelism ICLR 2024 (arXiv:2401.10241): https://arxiv.org/abs/2401.10241
- AdaPtis 2025 (arXiv:2509.23722): https://arxiv.org/pdf/2509.23722
- Seq1F1B NAACL 2025: https://aclanthology.org/2025.naacl-long.454.pdf
- PipeFill 2024: https://www.pdl.cmu.edu/PDL-FTP/BigLearning/Pipefill-2410.07192v1.pdf
- GPipe (arXiv:1811.06965): https://arxiv.org/abs/1811.06965
- PipeDream (arXiv:1806.03377): https://arxiv.org/abs/1806.03377

### Synthetic Gradients / DNI
- DeepMind DNI 2016 (arXiv:1608.05343): https://arxiv.org/abs/1608.05343
- Understanding Synthetic Gradients 2017 (arXiv:1703.00522): https://arxiv.org/abs/1703.00522
- Benchmarking DNI 2017 (arXiv:1712.08314): https://arxiv.org/abs/1712.08314

### Reservoir Computing / ESN
- RC as a Language Model 2025 (arXiv:2507.15779): https://arxiv.org/abs/2507.15779
- Syntactic Learnability of ESN at Scale 2025 (arXiv:2503.01724): https://arxiv.org/html/2503.01724v1
- Locally Connected ESN ICLR 2025: https://openreview.net/forum?id=KeRwLLwZaw

### Zeroth-Order
- MeZO Malladi et al. NeurIPS 2023: https://proceedings.neurips.cc/paper_files/paper/2023/file/a627810151be4d13f907ac898ff7e948-Paper-Conference.pdf
- MobiZO EMNLP 2025 (arXiv:2409.15520): https://arxiv.org/html/2409.15520v3
- ZeroQAT 2025 (arXiv:2509.00031): https://arxiv.org/abs/2509.00031
- Sparse MeZO 2024 (arXiv:2402.15751): https://arxiv.org/html/2402.15751
- AGZO 2026 (arXiv:2601.17261): https://arxiv.org/html/2601.17261v3
- MaZO Masked ZO 2025 (arXiv:2502.11513): https://arxiv.org/html/2502.11513v1
- Learning a ZO Optimizer 2025 (arXiv:2510.00419): https://arxiv.org/html/2510.00419v1
- ZeroFTL 2025 (arXiv:2511.11362): https://arxiv.org/html/2511.11362

### Low-Memory Optimizer (related)
- GaLore 2024 (arXiv:2403.03507): https://arxiv.org/abs/2403.03507
- MeBP 2025 (arXiv:2510.03425): https://arxiv.org/abs/2510.03425
- MobileFineTuner 2025 (arXiv:2512.08211): https://arxiv.org/abs/2512.08211

### Spiking
- SpikeGPT 2023 (arXiv:2302.13939): https://arxiv.org/abs/2302.13939
- SpikeLLM ICLR 2025 (arXiv:2407.04752): https://arxiv.org/abs/2407.04752
- SpikingBrain 2025 (arXiv:2509.05276): https://arxiv.org/abs/2509.05276

---

## One-paragraph TL;DR (for orchestrator handoff)

After full literature review of 13 paradigm families, **no nature/physics/biology-inspired learning rule has produced an LM-scale weight-trained model competitive with backprop**. The candidates that come closest (Holomorphic EP, μPC) top out at ImageNet 32×32 / Fashion-MNIST. SpikingBrain-76B is the lone "biologically inspired" LM at scale, but it is a Qwen2.5-derived sparsity reshape trained on a non-NVIDIA GPU cluster, not a different update rule and not phone-deployable. The operator-named "resonance-based" candidate has zero LM-scale evidence and zero SoC fit on Snapdragon (no oscillator primitive). The honest "natural fit" answer for SM8750 in 2026 is: **(1) Bubble-aware pipeline-parallel backprop using all three devices, (2) MeBP + MobiZO/MeZO hybrid for the trainable surfaces, (3) Quantization-aware on-device training for the deployed graph.** These three are not biologically poetic, but they are the only paradigms with measured Snapdragon-class receipts. Treat all "bio-inspired" candidates as Tier-2/3 research probes, not first-wave bets. Falsifiers explicitly named for each tier. `fp-demogravity` risk: simulating oscillators or settling dynamics on Hexagon NPU is a demo, not a learning system.
