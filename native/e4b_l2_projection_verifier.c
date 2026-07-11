/* Phone-local verifier for the frozen E4B W4/W2 projection gate.
 *
 * The program emits metrics only. Raw reference and candidate tensors never
 * need to leave the phone. Exit 0 means passed_scope, 2 means falsified_scope,
 * and 3 means an invalid invocation or unreadable/non-finite tensor.
 */

#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TOP_K 32u

typedef struct {
  double max_abs;
  double rms;
  double relative_l2;
  double cosine;
  double js_divergence;
  double top_k_overlap;
  int top_1_equal;
} Metrics;

typedef struct {
  float value;
  uint32_t index;
} RankedValue;

static int rank_before(const RankedValue left, const RankedValue right) {
  if (left.value > right.value) return 1;
  if (left.value < right.value) return 0;
  return left.index < right.index;
}

static int host_is_little_endian(void) {
  const uint16_t value = 1;
  return *((const uint8_t *)&value) == 1;
}

static void *read_exact(const char *path, const size_t expected_bytes) {
  FILE *handle = fopen(path, "rb");
  if (handle == NULL) {
    fprintf(stderr, "cannot open %s: %s\n", path, strerror(errno));
    return NULL;
  }
  void *data = malloc(expected_bytes == 0 ? 1 : expected_bytes);
  if (data == NULL) {
    fclose(handle);
    fprintf(stderr, "allocation failed for %s\n", path);
    return NULL;
  }
  const size_t count = fread(data, 1, expected_bytes, handle);
  const int extra = fgetc(handle);
  const int close_status = fclose(handle);
  if (count != expected_bytes || extra != EOF || close_status != 0) {
    fprintf(stderr, "size/read mismatch for %s\n", path);
    free(data);
    return NULL;
  }
  return data;
}

static float bf16_to_float(const uint16_t value) {
  const uint32_t bits = ((uint32_t)value) << 16;
  float result;
  memcpy(&result, &bits, sizeof(result));
  return result;
}

static float fp16_to_float(const uint16_t value) {
  const uint32_t sign = ((uint32_t)value & 0x8000u) << 16;
  const uint32_t exponent = ((uint32_t)value >> 10) & 0x1fu;
  uint32_t mantissa = (uint32_t)value & 0x03ffu;
  uint32_t bits;
  if (exponent == 0) {
    if (mantissa == 0) {
      bits = sign;
    } else {
      int shift = 0;
      while ((mantissa & 0x0400u) == 0) {
        mantissa <<= 1;
        ++shift;
      }
      mantissa &= 0x03ffu;
      bits = sign | ((uint32_t)(127 - 15 - shift) << 23) | (mantissa << 13);
    }
  } else if (exponent == 0x1fu) {
    bits = sign | 0x7f800000u | (mantissa << 13);
  } else {
    bits = sign | ((exponent + (127u - 15u)) << 23) | (mantissa << 13);
  }
  float result;
  memcpy(&result, &bits, sizeof(result));
  return result;
}

static int insert_ranked(RankedValue top[TOP_K], uint32_t *used, const RankedValue value) {
  uint32_t position = 0;
  while (position < *used && rank_before(top[position], value)) ++position;
  if (position >= TOP_K) return 0;
  const uint32_t end = *used < TOP_K ? *used : TOP_K - 1;
  for (uint32_t index = end; index > position; --index) top[index] = top[index - 1];
  top[position] = value;
  if (*used < TOP_K) ++(*used);
  return 1;
}

static void top_k(const float *values, const size_t count, RankedValue result[TOP_K]) {
  uint32_t used = 0;
  for (size_t index = 0; index < count; ++index) {
    const RankedValue value = {values[index], (uint32_t)index};
    insert_ranked(result, &used, value);
  }
}

static double js_divergence(const float *left, const float *right, const size_t count) {
  double left_max = -INFINITY;
  double right_max = -INFINITY;
  for (size_t index = 0; index < count; ++index) {
    if ((double)left[index] > left_max) left_max = left[index];
    if ((double)right[index] > right_max) right_max = right[index];
  }
  double left_sum = 0.0;
  double right_sum = 0.0;
  for (size_t index = 0; index < count; ++index) {
    left_sum += exp((double)left[index] - left_max);
    right_sum += exp((double)right[index] - right_max);
  }
  double divergence = 0.0;
  for (size_t index = 0; index < count; ++index) {
    const double p = exp((double)left[index] - left_max) / left_sum;
    const double q = exp((double)right[index] - right_max) / right_sum;
    const double midpoint = 0.5 * (p + q);
    if (p > 0.0) divergence += 0.5 * p * log(p / midpoint);
    if (q > 0.0) divergence += 0.5 * q * log(q / midpoint);
  }
  return divergence;
}

static int compute_metrics(const float *reference,
                           const float *candidate,
                           const size_t count,
                           const int with_distribution,
                           Metrics *metrics) {
  double squared_error = 0.0;
  double squared_reference = 0.0;
  double squared_candidate = 0.0;
  double dot = 0.0;
  metrics->max_abs = 0.0;
  for (size_t index = 0; index < count; ++index) {
    if (!isfinite(reference[index]) || !isfinite(candidate[index])) return 0;
    const double left = reference[index];
    const double right = candidate[index];
    const double error = right - left;
    const double absolute = fabs(error);
    if (absolute > metrics->max_abs) metrics->max_abs = absolute;
    squared_error += error * error;
    squared_reference += left * left;
    squared_candidate += right * right;
    dot += left * right;
  }
  metrics->rms = sqrt(squared_error / (double)count);
  metrics->relative_l2 = squared_reference > 0.0 ? sqrt(squared_error / squared_reference) : INFINITY;
  metrics->cosine = squared_reference > 0.0 && squared_candidate > 0.0
                        ? dot / sqrt(squared_reference * squared_candidate)
                        : 0.0;
  metrics->js_divergence = 0.0;
  metrics->top_k_overlap = 0.0;
  metrics->top_1_equal = 0;
  if (with_distribution) {
    RankedValue reference_top[TOP_K];
    RankedValue candidate_top[TOP_K];
    top_k(reference, count, reference_top);
    top_k(candidate, count, candidate_top);
    uint32_t overlap = 0;
    for (uint32_t left_index = 0; left_index < TOP_K; ++left_index) {
      for (uint32_t right_index = 0; right_index < TOP_K; ++right_index) {
        if (reference_top[left_index].index == candidate_top[right_index].index) {
          ++overlap;
          break;
        }
      }
    }
    metrics->top_k_overlap = (double)overlap / (double)TOP_K;
    metrics->top_1_equal = reference_top[0].index == candidate_top[0].index;
    metrics->js_divergence = js_divergence(reference, candidate, count);
  }
  return isfinite(metrics->max_abs) && isfinite(metrics->rms) && isfinite(metrics->relative_l2) &&
         isfinite(metrics->cosine) && isfinite(metrics->js_divergence);
}

static int w2_passes(const Metrics metrics,
                     const double max_abs,
                     const double rms,
                     const double relative_l2,
                     const double cosine,
                     const double js,
                     const double overlap) {
  return metrics.max_abs <= max_abs && metrics.rms <= rms && metrics.relative_l2 <= relative_l2 &&
         metrics.cosine >= cosine && metrics.js_divergence <= js &&
         metrics.top_k_overlap >= overlap && metrics.top_1_equal;
}

static void print_metrics(const char *name, const Metrics value) {
  printf("\"%s\":{\"cosine\":%.17g,\"max_abs\":%.17g,"
         "\"relative_l2\":%.17g,\"rms\":%.17g,"
         "\"softmax_js_divergence\":%.17g,\"top_1_equal\":%s,"
         "\"top_k_set_overlap\":%.17g}",
         name,
         value.cosine,
         value.max_abs,
         value.relative_l2,
         value.rms,
         value.js_divergence,
         value.top_1_equal ? "true" : "false",
         value.top_k_overlap);
}

static int verify_w4(const char *reference_path, const char *candidate_path, const size_t count) {
  int8_t *reference_raw = read_exact(reference_path, count);
  int8_t *candidate_raw = read_exact(candidate_path, count);
  if (reference_raw == NULL || candidate_raw == NULL) {
    free(reference_raw);
    free(candidate_raw);
    return 3;
  }
  float *reference = malloc(count * sizeof(float));
  float *candidate = malloc(count * sizeof(float));
  if (reference == NULL || candidate == NULL) {
    free(reference_raw);
    free(candidate_raw);
    free(reference);
    free(candidate);
    return 3;
  }
  int reference_nonzero = 0;
  for (size_t index = 0; index < count; ++index) {
    reference[index] = reference_raw[index];
    candidate[index] = candidate_raw[index];
    if (reference_raw[index] != 0) reference_nonzero = 1;
  }
  Metrics metrics = {0};
  const int computed = compute_metrics(reference, candidate, count, 0, &metrics);
  const int passed = computed && reference_nonzero && metrics.max_abs <= 1.0 && metrics.rms <= 0.25 &&
                     metrics.cosine >= 0.99999;
  printf("{\"mode\":\"w4\",\"reference_nonzero\":%s,\"state\":\"%s\",",
         reference_nonzero ? "true" : "false",
         passed ? "passed_scope" : "falsified_scope");
  print_metrics("qat_to_qnn", metrics);
  printf("}\n");
  free(reference_raw);
  free(candidate_raw);
  free(reference);
  free(candidate);
  return passed ? 0 : 2;
}

static int verify_w2(const char *authority_path,
                     const char *surrogate_path,
                     const char *candidate_path,
                     const size_t count) {
  uint16_t *authority_raw = read_exact(authority_path, count * sizeof(uint16_t));
  uint16_t *surrogate_raw = read_exact(surrogate_path, count * sizeof(uint16_t));
  uint16_t *candidate_raw = read_exact(candidate_path, count * sizeof(uint16_t));
  if (authority_raw == NULL || surrogate_raw == NULL || candidate_raw == NULL) {
    free(authority_raw);
    free(surrogate_raw);
    free(candidate_raw);
    return 3;
  }
  float *authority = malloc(count * sizeof(float));
  float *surrogate = malloc(count * sizeof(float));
  float *candidate = malloc(count * sizeof(float));
  if (authority == NULL || surrogate == NULL || candidate == NULL) {
    free(authority_raw);
    free(surrogate_raw);
    free(candidate_raw);
    free(authority);
    free(surrogate);
    free(candidate);
    return 3;
  }
  for (size_t index = 0; index < count; ++index) {
    authority[index] = bf16_to_float(authority_raw[index]);
    surrogate[index] = fp16_to_float(surrogate_raw[index]);
    candidate[index] = fp16_to_float(candidate_raw[index]);
  }
  Metrics cast_edge = {0};
  Metrics conversion_edge = {0};
  Metrics combined_edge = {0};
  const int computed = compute_metrics(authority, surrogate, count, 1, &cast_edge) &&
                       compute_metrics(surrogate, candidate, count, 1, &conversion_edge) &&
                       compute_metrics(authority, candidate, count, 1, &combined_edge);
  const int cast_pass = computed && w2_passes(cast_edge, 0.125, 0.02, 0.005, 0.99999, 1.0e-6, 0.96875);
  const int conversion_pass = computed &&
                              w2_passes(conversion_edge, 0.0625, 0.01, 0.0025, 0.999995, 5.0e-7, 0.96875);
  const int combined_pass = computed &&
                            w2_passes(combined_edge, 0.1875, 0.03, 0.0075, 0.99998, 2.0e-6, 0.9375);
  const int passed = cast_pass && conversion_pass && combined_pass;
  printf("{\"mode\":\"w2\",\"state\":\"%s\",",
         passed ? "passed_scope" : "falsified_scope");
  print_metrics("bf16_to_fp16_framework", cast_edge);
  printf(",");
  print_metrics("fp16_framework_to_qnn", conversion_edge);
  printf(",");
  print_metrics("bf16_qat_to_qnn_combined", combined_edge);
  printf("}\n");
  free(authority_raw);
  free(surrogate_raw);
  free(candidate_raw);
  free(authority);
  free(surrogate);
  free(candidate);
  return passed ? 0 : 2;
}

int main(const int argc, char **argv) {
  if (!host_is_little_endian()) {
    fprintf(stderr, "little-endian host required\n");
    return 3;
  }
  if (argc < 5) {
    fprintf(stderr,
            "usage: %s w4 REFERENCE_S8 CANDIDATE_S8 COUNT\n"
            "       %s w2 AUTHORITY_BF16 SURROGATE_F16 CANDIDATE_F16 COUNT\n",
            argv[0],
            argv[0]);
    return 3;
  }
  char *end = NULL;
  const unsigned long long parsed = strtoull(argv[argc - 1], &end, 10);
  if (end == argv[argc - 1] || *end != '\0' || parsed == 0 || parsed > UINT32_MAX) {
    fprintf(stderr, "invalid element count\n");
    return 3;
  }
  if (strcmp(argv[1], "w4") == 0 && argc == 5) {
    return verify_w4(argv[2], argv[3], (size_t)parsed);
  }
  if (strcmp(argv[1], "w2") == 0 && argc == 6) {
    return verify_w2(argv[2], argv[3], argv[4], (size_t)parsed);
  }
  fprintf(stderr, "invalid mode or argument count\n");
  return 3;
}
