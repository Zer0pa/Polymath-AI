# Training Systems For Heterogeneous SoC Architectures

**Date:** 2026-05-16  
**Role:** Research Agent B  
**Scope:** Snapdragon 8 Elite / RedMagic 10 Pro-class Android SoC: Oryon CPU, Adreno GPU, Hexagon NPU, unified DRAM, active cooling.  
**Question:** what does forward/backward become if the model is designed for heterogeneous SoC training rather than copied from cloud-GPU training?

## Verdict

The viable near-term architecture is **frozen dense trunk plus trainable faculty/adapters/head/norms**, with the frozen trunk compiled as large NPU-forward islands and the trainable surfaces updated on Adreno/CPU or by forward-only zeroth-order probes.

Training different layers or experts in parallel is mathematically valid only in one of these cases:

1. **Exact pipeline/model parallelism:** the computation graph is unchanged; devices overlap forward/backward for different microbatches, with synchronization or weight versioning. This is exact or near-exact training of the same global objective, but it does not remove backprop's dependency chain inside one sample.
2. **Exact sparse MoE objective:** the model objective explicitly routes tokens to experts; selected experts can train in parallel on their routed tokens. The router, load balancing, and inactive-expert starvation become part of the objective and risk surface.
3. **Surrogate/local objective:** layers or modules use local losses, synthetic gradients, delayed gradients, or auxiliary heads. This is no longer exact next-token backprop unless the approximation is later corrected or empirically shown not to regress the authority metric.
4. **Frozen-base adaptation:** only side modules are trainable. Backward is exact for the adapter objective, but the frozen trunk cannot internalize new global representations.
5. **Zeroth-order adaptation:** backward is replaced by multiple forward passes estimating gradients. Memory improves, but sample/forward-pass variance can dominate wall-clock.

For Polymath-AI, the governing objective should stay **time-to-valid authority metric under falsifier telemetry**, not "more TOPS used." A faster local or modular method that degrades validation loss, ELO, retention, or domain eval is a failed training system.

## What The Pass Becomes

### Standard Dense Backprop

```text
forward:
  x_0 = tokens
  x_l = block_l(x_{l-1}) for l = 1..L
  loss = CE(head(x_L), target)

backward:
  delta_L = d loss / d x_L
  delta_{l-1}, grad_theta_l = vjp(block_l, delta_l)
  update all theta_l
```

This is mathematically clean but poorly matched to Snapdragon NPU training. Qualcomm and PyTorch edge stacks publicly expose NPU paths primarily as compiled inference/deployment runtimes; Qualcomm AI Hub also warns that NPU fallback happens when ops/ranks/types are unsupported. Full backprop needs activations, trainable weights, optimizer state, and backward kernels, so the Hexagon NPU should be treated as a frozen forward accelerator until proven otherwise on-device.

### Local / Faculty Training

```text
split model into modules M_i
forward:
  z_i = M_i(z_{i-1}) or faculty_i(shared_state, task_state)
  local_loss_i = aux_i(z_i, target/teacher/contrastive signal)

local backward:
  update theta_i from d local_loss_i / d theta_i
  optionally update interface adapters / routers
```

This removes update locking by changing the objective. It is not exact global backprop unless local gradients are unbiased or sufficiently accurate approximations of the global gradient. The risk is local feature learning that looks good at intermediate heads but hurts the final authority metric.

### Synthetic / Delayed Gradients

```text
module M_i predicts z_i
gradient model G_i predicts d global_loss / d z_i
M_i updates from G_i(z_i, optional target/context)
later true gradients train/calibrate G_i
```

This is a learned gradient interface. It can update modules asynchronously, but the central failure mode is gradient-model drift: the module optimizes what the synthetic gradient predicts, not necessarily the real objective.

### Sparse Expert / MoE Training

```text
router chooses expert set E(x)
experts process routed tokens independently
loss includes task loss plus routing/load-balance terms
backward updates router and active experts only
```

Experts can be trained in parallel for the exact MoE objective. On a phone SoC, dynamic token-level routing is a weak first target because top-k, scatter/gather, many small matmuls, load balancing, and backend transfers can dominate. A static faculty bank selected per task/domain/batch is much more plausible than dynamic per-token MoE on Hexagon.

### Adapter / LoRA / Frozen-Base Training

```text
frozen trunk: NPU compiled forward island
trainable sidecar: LoRA/adapters/norm/head on GPU or CPU
backward: only sidecar parameters require gradients
```

This is the strongest current fit. The trunk can stay quantized/static, while adapters remain small enough for Adreno/CPU training. The tradeoff is representational ceiling: new knowledge may be expressed as a side behavior rather than absorbed into the base model.

### Zeroth-Order / Forward-Only Training

```text
sample perturbation u over trainable parameters
loss_plus  = loss(theta + eps*u)
loss_minus = loss(theta - eps*u)
grad_est = (loss_plus - loss_minus) * u / (2*eps)
update theta
```

This avoids activation storage and can reuse inference engines. It is attractive only if repeated forward passes are cheap and parallelizable. On Snapdragon, that must be measured: graph compile/repack, backend crossings, and thermal throttling can erase the theoretical memory win.

## Architecture-Training Compatibility

| Architecture | Parallel training validity | SoC fit | Verdict | Regression risks |
|---|---|---|---|---|
| Dense transformer | Exact with normal backprop; exact pipeline parallelism across microbatches/stages if synchronization preserves the same minibatch update; approximate if using stale gradients. | Strong for frozen NPU forward plus GPU/CPU sidecar; weak for full on-phone backprop. | Use as baseline trunk. Do not claim NPU training until backward placement is proven. | Activation memory, optimizer state, graph breaks, silent CPU/GPU fallback, local speedups that worsen final loss. |
| Sparse MoE | Exact for an explicitly routed MoE objective; experts train in parallel on routed tokens. Independent expert training without router/global loss is a different objective. | Weak first target for dynamic token MoE; medium for static domain/faculty expert bank. | Use static faculty selection before dynamic MoE. | Route collapse, undertrained experts, load-balance loss gaming, scatter/gather overhead, expert specialization that hurts general eval. |
| Nested / MatFormer | Valid as joint multi-granularity training of nested submodels, not as independent layer training. | Good for elastic inference and device-specific extraction; not a direct training-throughput fix. | Useful later for one checkpoint serving multiple phone budgets. | Submodel interference, smaller extracted model passes cheap eval but regresses authority tasks. |
| SSM / hybrid | Exact backprop through scan/state kernels if implemented; some scan structure is parallelizable, but not automatically NPU-supported. | Medium on Adreno custom kernels; uncertain on Hexagon/QNN. | Research path after dense baseline. | Custom backward kernels, weaker content reasoning at some scales, unproven phone runtime support, benchmark cherry-picking. |
| Adapter / faculty modular | Exact for frozen-base adapter objective; faculties can train in parallel across domains/tasks/examples. Not exact full-model learning. | Strongest near-term fit. | Primary candidate. | Frozen trunk ceiling, adapter interference, domain overfit, boundary copy cost, false belief that adapter success equals pretraining. |
| Micro/mobile models | Exact full or partial backprop if model is small enough for Adreno/CPU memory; NPU still mostly forward. | Medium; useful for calibration, ablations, and small domain models. | Viable for honest small-model training, not a substitute for 3B+ authority unless metric proves it. | "Toy pass" risk, small-model plateau, training speed mistaken for useful capability. |

## Viable Now

| Method | Use now? | Why |
|---|---:|---|
| Frozen dense trunk + LoRA/adapters/head/norm | Yes | Matches public edge stacks: compiled inference forward plus small trainable surfaces. LoRA and adapters have strong literature support. |
| Static faculty/domain adapter bank | Yes | Parallelizes across domains/tasks without dynamic token dispatch. Keeps graph static and auditable. |
| Exact pipeline over CPU/GPU custom kernels | Conditional | Mathematically sound, but a phone has few heterogeneous devices and high boundary overhead. Use only if profiler shows stage overlap beats transfer cost. |
| Zeroth-order LoRA/adapters via inference engine | Conditional | Strong memory story and directly relevant edge work exists, but forward-pass count and thermal behavior must be measured. |
| Micro/mobile model fine-tuning | Conditional | Good for falsifiers and substrate learning. Authority metric must not be relaxed because the model is small. |

## Research-Viable But Not First

| Method | Status | Why not first |
|---|---|---|
| Local auxiliary losses / greedy layerwise learning | Evidence exists in vision and some language settings. | Optimizes surrogate losses; final task regression is the main risk. Needs final-metric gate and probably end-to-end correction. |
| Synthetic gradients / decoupled neural interfaces | Valid research direction for asynchronous modules. | Gradient predictors can drift; not a production-proven LLM pretraining path. |
| Delayed-gradient decoupled backprop | Has convergence results under assumptions. | Staleness and optimizer interaction must be bounded on real training, not assumed. |
| Dynamic MoE | Proven at datacenter scale. | Phone routing and many-small-kernel behavior likely lose to static dense blocks before quality is measured. |
| MatFormer / MatMamba | Promising for elastic deployment. | Does not remove the need to train a large universal model; helps deployment more than phone-side training. |

## Speculative For This Gate

Forward-Forward, predictive coding, and deep equilibrium methods are not first-wave Polymath training systems. They are relevant only as research comparisons for local or backward-free learning. Forward-Forward is explicitly preliminary and demonstrated on small problems. Predictive coding can match or approximate backprop under specific formulations, but published work flags extra computational cost and non-trivial requirements. Deep equilibrium models trade explicit depth for fixed-point solving and implicit differentiation; that is not an obvious Snapdragon advantage before dense and adapter baselines are falsified.

## Implementation Implications

1. Build the authority baseline first: dense transformer trunk, frozen-middle or frozen-trunk adaptation, standard validation loss, retention tests, ELO/domain gates, thermal and backend placement receipts.
2. Add faculty adapters as explicit modules: `router_or_policy -> adapter_set -> audited objective`. Start with static per-domain routing, then test learned routing only if static routing passes.
3. Treat local losses as an experimental optimizer, not a free speedup. Every local objective must report final global loss and domain regressions.
4. Keep NPU islands large and static. Avoid per-step graph mutation, token-level dynamic routing, and many small NPU/GPU crossings.
5. For zeroth-order methods, measure forward-query cost under warm thermal state. The metric is examples/sec to target validation loss, not memory saved in isolation.
6. If trying layer parallelism, use exact pipeline schedules first. Only then test delayed/synthetic/local updates against the same authority metric.

## Uncertainty Flags

- Public Qualcomm/ExecuTorch/AI Hub documentation supports a strong inference/deployment conclusion, but does not prove the RedMagic 10 Pro firmware exposes all needed QNN/HTP paths for Polymath shapes. Phone receipts remain the authority.
- There is no public primary-source evidence that Snapdragon 8 Elite Hexagon NPU is a general autograd/backward training target for transformer pretraining.
- Local and decoupled learning papers show real signal, but evidence is not equivalent to modern LLM pretraining at the scale and quality target Polymath cares about.
- MoE speedups reported on TPU/GPU clusters do not transfer automatically to one mobile SoC with shared DRAM and backend-specific buffers.

## Source URLs

- Snapdragon 8 Elite official platform page: https://www.qualcomm.com/smartphones/products/8-series/snapdragon-8-elite-mobile-platform
- Qualcomm AI Engine Direct SDK: https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- Qualcomm AI Hub FAQ on compile/profile/inference, fallback, compute units: https://app.aihub.qualcomm.com/docs/hub/faq.html
- ExecuTorch edge inference docs: https://docs.pytorch.org/executorch/stable/
- Decoupled Neural Interfaces using Synthetic Gradients: https://arxiv.org/abs/1608.05343
- Greedy Layerwise Learning Can Scale to ImageNet: https://arxiv.org/abs/1812.11446
- Parallel Training of Deep Networks with Local Updates: https://arxiv.org/abs/2012.03837
- Decoupled Parallel Backpropagation with Convergence Guarantee: https://arxiv.org/abs/1804.10574
- GPipe pipeline parallelism: https://arxiv.org/abs/1811.06965
- PipeDream pipeline parallelism: https://arxiv.org/abs/1806.03377
- Switch Transformers / sparse MoE: https://arxiv.org/abs/2101.03961
- Mixture-of-Experts with Expert Choice Routing: https://arxiv.org/abs/2202.09368
- MatFormer nested transformer: https://arxiv.org/abs/2310.07707
- Mamba selective SSM: https://arxiv.org/abs/2312.00752
- Mamba-2 / structured state space duality: https://arxiv.org/abs/2405.21060
- MatMamba: https://arxiv.org/abs/2410.06718
- LoRA: https://arxiv.org/abs/2106.09685
- Adapter modules / parameter-efficient transfer: https://arxiv.org/abs/1902.00751
- MeZO / fine-tuning with just forward passes: https://arxiv.org/abs/2305.17333
- MobiZO edge fine-tuning via inference engines: https://arxiv.org/abs/2409.15520
- Zeroth-order fine-tuning with extreme sparsity: https://arxiv.org/abs/2406.02913
- Forward-Forward Algorithm: https://arxiv.org/abs/2212.13345
- Predictive Coding Can Do Exact Backpropagation on CNNs and RNNs: https://arxiv.org/abs/2103.03725
- MobileLLM sub-billion on-device models: https://arxiv.org/abs/2402.14905
