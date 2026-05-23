# H11-E Falsifier Report

- phone-local candidate daemon trials used `phase11_runner`; host did not drive individual training iterations.
- rank-4 baseline and two expanded residual ranks were run with identical token-cache cadence and learning rate.
- projection LoRA/DoRA across q/o/gate/up was not promoted because the current authority backward path does not implement those layer-internal gradients.
- selected rank: 4.
- gate status: fail.
