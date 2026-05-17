// Skeleton only. Do not use for correctness claims until wired to the golden gate.

__kernel void rmsnorm_forward_f32(__global const float* input,
                                  __global const float* weight,
                                  __global float* output,
                                  const unsigned int rows,
                                  const unsigned int width,
                                  const float epsilon) {
  (void)input;
  (void)weight;
  (void)output;
  (void)rows;
  (void)width;
  (void)epsilon;
}

__kernel void rmsnorm_backward_f32(__global const float* input,
                                   __global const float* weight,
                                   __global const float* grad_output,
                                   __global float* grad_input,
                                   __global float* grad_weight,
                                   const unsigned int rows,
                                   const unsigned int width,
                                   const float epsilon) {
  (void)input;
  (void)weight;
  (void)grad_output;
  (void)grad_input;
  (void)grad_weight;
  (void)rows;
  (void)width;
  (void)epsilon;
}

__kernel void matmul_forward_f32(__global const float* lhs,
                                 __global const float* rhs,
                                 __global float* output,
                                 const unsigned int rows,
                                 const unsigned int shared,
                                 const unsigned int cols) {
  (void)lhs;
  (void)rhs;
  (void)output;
  (void)rows;
  (void)shared;
  (void)cols;
}

__kernel void matmul_backward_f32(__global const float* lhs,
                                  __global const float* rhs,
                                  __global const float* grad_output,
                                  __global float* grad_lhs,
                                  __global float* grad_rhs,
                                  const unsigned int rows,
                                  const unsigned int shared,
                                  const unsigned int cols) {
  (void)lhs;
  (void)rhs;
  (void)grad_output;
  (void)grad_lhs;
  (void)grad_rhs;
  (void)rows;
  (void)shared;
  (void)cols;
}
