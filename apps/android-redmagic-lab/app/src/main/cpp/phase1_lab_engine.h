#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define POLYMATH_PHASE1_ENGINE_ABI_VERSION 4u
#define POLYMATH_PHASE1_RUN_FLAG_RUNTIME_SAMPLER 1u
#define POLYMATH_PHASE1_RUN_FLAG_NATIVE_WARM_SEQUENCE 2u
#define POLYMATH_PHASE1_RUN_FLAG_NATIVE_EXTENDED_WARM_SEQUENCE 4u
#define POLYMATH_PHASE1_RUN_FLAG_DIRECT_ENTRY 8u
#define POLYMATH_PHASE1_RUN_FLAG_CHILD_EXEC 16u

typedef struct phase1_engine phase1_engine_t;

typedef struct {
    uint32_t abi_version;
    const char* build_id;
    const char* git_sha;
    const char* engine_name;
    const char* connection_state;
} phase1_engine_info_t;

typedef struct {
    const char* tokenizer_dir;
    const char* gbt1_path;
    const char* batch_list_path;
    const char* qai1_path;
    const char* pqa1_output_path;
    const char* report_output_path;
    const char* batch_metrics_output_path;
    const char* bpe_metrics_output_path;
    const char* bpe_algorithm;
    const char* phase1_exec_path;
    uint32_t worker_count;
    uint32_t batch_hint;
    uint32_t flags;
} phase1_run_config_t;

typedef struct {
    uint64_t records;
    uint64_t token_ids;
    uint64_t distinct_token_ids;
    uint32_t vocab_size;
    double wall_sec;
    double vocab_coverage_ratio;
    double tokens_per_record_mean;
    double tokens_per_record_p50;
    double tokens_per_record_p95;
    double tokens_per_record_p99;
    uint64_t input_bytes;
    uint64_t output_bytes;
    double input_mb_per_sec;
    double token_ids_per_sec;
    double records_per_sec;
    double latency_ms_per_record;
    uint64_t pss_kb;
    uint64_t rss_kb;
    uint64_t peak_rss_kb;
    uint32_t job_count;
    uint32_t thread_count;
    uint64_t hot_loop_allocations;
    uint64_t span_errors;
    uint64_t parity_mismatches;
    char material_hash_hex[65];
    char cpuset_before[128];
    char cpuset_after[128];
    char cpus_allowed_list_before[128];
    char cpus_allowed_list_after[128];
    char error_message[512];
} phase1_run_result_t;

int phase1_engine_create(const char* app_files_dir, phase1_engine_t** out);
int phase1_engine_info(phase1_engine_t* engine, phase1_engine_info_t* out);
int phase1_engine_run(
    phase1_engine_t* engine,
    const phase1_run_config_t* config,
    phase1_run_result_t* out
);
void phase1_engine_destroy(phase1_engine_t* engine);

#ifdef __cplusplus
}
#endif
