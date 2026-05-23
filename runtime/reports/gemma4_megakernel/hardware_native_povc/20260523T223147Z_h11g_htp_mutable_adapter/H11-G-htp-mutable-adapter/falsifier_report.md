# H11-G Falsifier Report

- HTP frozen-forward inference is accepted only if `qnn-net-run` completes on the phone with `qnn_partition_0` and one inference.
- Mutable-section promotion is rejected unless the active context reports updateable tensors and an update binary is applied on phone.
- Zero-order promotion is rejected unless two or more forward-only perturbation/evaluation/apply steps improve the declared objective without host gradients or optimizer substitution.
- Normal HTP backprop remains false: no backward, gradient, or optimizer QNN/HTP API was found or executed.
