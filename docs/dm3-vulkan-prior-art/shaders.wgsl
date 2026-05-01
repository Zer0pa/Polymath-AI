// DM3 Physics Kernels (WGSL)

struct FieldState {
    data: array<f32>, // [VertexCount * 192]
};

struct Neighbor {
    index: u32,
    weight: f32,
};

struct Adjacency {
    // Fixed max degree 12 for V1
    data: array<Neighbor>, // [VertexCount * 12]
};

struct Params {
    dt: f32,
    alpha: f32, // Diffusion rate
    beta: f32,  // Non-linearity strength
    vertex_count: u32,
    d_model: u32, // 192
};

@group(0) @binding(0) var<storage, read_write> state_in: FieldState;
@group(0) @binding(1) var<storage, read_write> state_out: FieldState;
@group(0) @binding(2) var<storage, read> adjacency: Adjacency;
@group(0) @binding(3) var<uniform> params: Params;

// Kernel: k_relax (Fused Laplacian + Non-linearity)
// x' = x + dt * (alpha * L(x) + beta * sigma(x))
@compute @workgroup_size(64)
fn k_relax(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let idx = global_id.x;
    if (idx >= params.vertex_count) {
        return;
    }

    let d = params.d_model;
    let base_idx = idx * d;
    let neighbor_base = idx * 12u;

    for (var i = 0u; i < d; i = i + 1u) {
        let current_val = state_in.data[base_idx + i];
        
        // Laplacian L(x)
        var laplacian = 0.0;
        for (var n = 0u; n < 12u; n = n + 1u) {
            let n_idx = adjacency.data[neighbor_base + n].index;
            let weight = adjacency.data[neighbor_base + n].weight;
            
            if (n_idx != 0xFFFFFFFFu) {
                let neighbor_val = state_in.data[n_idx * d + i];
                laplacian = laplacian + weight * (neighbor_val - current_val);
            }
        }

        // Non-linearity sigma(x) = x / (1 + |x|)
        let sigma = current_val / (1.0 + abs(current_val));

        // Update
        let delta = params.alpha * laplacian + params.beta * sigma;
        state_out.data[base_idx + i] = current_val + params.dt * delta;
    }
}

// Kernel: k_ecc (Euler Characteristic Curve)
struct Histogram {
    bins: array<atomic<u32>, 64>,
};

@group(0) @binding(4) var<storage, read_write> ecc_hist: Histogram;

@compute @workgroup_size(64)
fn k_ecc(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let idx = global_id.x;
    if (idx >= params.vertex_count) {
        return;
    }

    let d = params.d_model;
    let base_idx = idx * d;

    // Magnitude
    var mag_sq = 0.0;
    for (var i = 0u; i < d; i = i + 1u) {
        let val = state_in.data[base_idx + i];
        mag_sq = mag_sq + val * val;
    }
    let mag = sqrt(mag_sq);

    // Binning [0, 10.0] -> [0, 63]
    let bin = u32(clamp(mag * 6.3, 0.0, 63.0));
    atomicAdd(&ecc_hist.bins[bin], 1u);
}

// Kernel: k_holography (Boundary -> Bulk Reconstruction Error)
// Computes error between actual bulk state and reconstructed state from boundary.
// For V1, simplified to: err = || x_bulk - avg(neighbors_boundary) ||
struct HoloError {
    total_error: atomic<u32>, // Fixed point accumulation
};

@group(0) @binding(5) var<storage, read_write> holo_err: HoloError;

@compute @workgroup_size(64)
fn k_holography(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let idx = global_id.x;
    if (idx >= params.vertex_count) {
        return;
    }
    
    // Only compute for bulk nodes (simplified check: degree > 3 implies bulk in some meshes)
    // Real implementation would use a mask.
    
    let d = params.d_model;
    let base_idx = idx * d;
    let neighbor_base = idx * 12u;

    var recon_error = 0.0;
    
    for (var i = 0u; i < d; i = i + 1u) {
        let current_val = state_in.data[base_idx + i];
        var neighbor_sum = 0.0;
        var count = 0.0;
        
        for (var n = 0u; n < 12u; n = n + 1u) {
            let n_idx = adjacency.data[neighbor_base + n].index;
            if (n_idx != 0xFFFFFFFFu) {
                neighbor_sum = neighbor_sum + state_in.data[n_idx * d + i];
                count = count + 1.0;
            }
        }
        
        if (count > 0.0) {
            let reconstructed = neighbor_sum / count;
            let diff = current_val - reconstructed;
            recon_error = recon_error + diff * diff;
        }
    }
    
    // Accumulate error (scaled to u32 for atomic add)
    let err_fixed = u32(recon_error * 1000.0);
    atomicAdd(&holo_err.total_error, err_fixed);
}

// Kernel: k_spectral (Principal Component Tracking)
// Simplified: Projects state onto random probe vector to track dominant mode.
struct SpectralState {
    projection: atomic<i32>, // Signed fixed point
};

@group(0) @binding(6) var<storage, read_write> spectral: SpectralState;
@group(0) @binding(7) var<storage, read> probe_vector: FieldState; // Random probe

@compute @workgroup_size(64)
fn k_spectral(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let idx = global_id.x;
    if (idx >= params.vertex_count) {
        return;
    }

    let d = params.d_model;
    let base_idx = idx * d;
    
    var dot_prod = 0.0;
    for (var i = 0u; i < d; i = i + 1u) {
        dot_prod = dot_prod + state_in.data[base_idx + i] * probe_vector.data[base_idx + i];
    }
    
    // Accumulate (scaled)
    let val_fixed = i32(dot_prod * 1000.0);
    atomicAdd(&spectral.projection, val_fixed);
}

// Kernel: k_transformer (Micro-Tx)
// Implements adjacency-masked attention + MLP
@compute @workgroup_size(64)
fn k_transformer(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let idx = global_id.x;
    if (idx >= params.vertex_count) {
        return;
    }

    let d = params.d_model;
    let base_idx = idx * d;
    let neighbor_base = idx * 12u;

    // 1. Resonance Attention (Weighted Average)
    for (var i = 0u; i < d; i = i + 1u) {
        var context_sum = 0.0;
        var count = 0.0;
        
        // Self
        context_sum = context_sum + state_in.data[base_idx + i];
        count = count + 1.0;

        // Neighbors
        for (var n = 0u; n < 12u; n = n + 1u) {
            let n_idx = adjacency.data[neighbor_base + n].index;
            if (n_idx != 0xFFFFFFFFu) {
                context_sum = context_sum + state_in.data[n_idx * d + i];
                count = count + 1.0;
            }
        }
        
        let mean = context_sum / count;
        
        // 2. MLP (Non-linear activation)
        let output = mean / (1.0 + abs(mean));
        
        // Residual Update
        state_out.data[base_idx + i] = state_in.data[base_idx + i] + params.dt * (output - state_in.data[base_idx + i]);
    }
}


// Kernel: kernel_matmul_vec (Matrix-Vector Multiplication)
// Computes: Output = Input * Weights^T
// Input: [Batch x In], Weights: [Out x In], Output: [Batch x Out]

struct MatMulParams {
    batch_size: u32,
    in_features: u32,
    out_features: u32,
    _pad: u32,
};

@group(0) @binding(0) var<storage, read> mm_input: array<f32>;
@group(0) @binding(1) var<storage, read> mm_weights: array<f32>;
@group(0) @binding(2) var<storage, read_write> mm_output: array<f32>;
@group(0) @binding(3) var<uniform> mm_params: MatMulParams;

@compute @workgroup_size(64)
fn kernel_matmul_vec(@builtin(global_invocation_id) global_id: vec3<u32>) {
    let idx = global_id.x;
    let total_outputs = mm_params.batch_size * mm_params.out_features;
    
    if (idx >= total_outputs) {
        return;
    }

    let b = idx / mm_params.out_features;
    let o = idx % mm_params.out_features;

    let in_features = mm_params.in_features;
    let input_offset = b * in_features;
    let weight_offset = o * in_features;

    var sum = 0.0;
    for (var i = 0u; i < in_features; i = i + 1u) {
        sum = sum + mm_input[input_offset + i] * mm_weights[weight_offset + i];
    }

    mm_output[idx] = sum;
}
