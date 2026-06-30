#include "phase1_lab_engine.h"

#include <android/log.h>
#include <jni.h>

#include <memory>
#include <sstream>
#include <string>

namespace {
constexpr const char* kLogTag = "PolymathLabNative";

struct EngineDeleter {
    void operator()(phase1_engine_t* engine) const {
        phase1_engine_destroy(engine);
    }
};

std::string jstring_to_string(JNIEnv* env, jstring value) {
    if (value == nullptr) {
        return {};
    }
    const char* chars = env->GetStringUTFChars(value, nullptr);
    if (chars == nullptr) {
        return {};
    }
    std::string result(chars);
    env->ReleaseStringUTFChars(value, chars);
    return result;
}

std::string json_escape(const std::string& value) {
    std::ostringstream escaped;
    for (char character : value) {
        switch (character) {
            case '\\':
                escaped << "\\\\";
                break;
            case '"':
                escaped << "\\\"";
                break;
            case '\n':
                escaped << "\\n";
                break;
            case '\r':
                escaped << "\\r";
                break;
            case '\t':
                escaped << "\\t";
                break;
            default:
                escaped << character;
                break;
        }
    }
    return escaped.str();
}

jstring to_jstring(JNIEnv* env, const std::string& value) {
    return env->NewStringUTF(value.c_str());
}

std::string engine_info_json(const std::string& app_files_dir) {
    phase1_engine_t* raw_engine = nullptr;
    const int create_result = phase1_engine_create(app_files_dir.c_str(), &raw_engine);
    std::unique_ptr<phase1_engine_t, EngineDeleter> engine(raw_engine);
    if (create_result != 0 || !engine) {
        return "{\"schema_version\":\"native_engine_info_v1\",\"connection_state\":\"BLOCKED\",\"error\":\"phase1_engine_create failed\"}";
    }

    phase1_engine_info_t info{};
    const int info_result = phase1_engine_info(engine.get(), &info);
    if (info_result != 0) {
        return "{\"schema_version\":\"native_engine_info_v1\",\"connection_state\":\"BLOCKED\",\"error\":\"phase1_engine_info failed\"}";
    }

    std::ostringstream json;
    json << "{"
         << "\"schema_version\":\"native_engine_info_v1\","
         << "\"abi_version\":" << info.abi_version << ","
         << "\"build_id\":\"" << json_escape(info.build_id) << "\","
         << "\"git_sha\":\"" << json_escape(info.git_sha) << "\","
         << "\"engine_name\":\"" << json_escape(info.engine_name) << "\","
         << "\"connection_state\":\"" << json_escape(info.connection_state) << "\","
         << "\"probe_state\":\"PROBE\","
         << "\"phase1_source_sha256\":\"829da5e89cf2c787dd6e1e2f984e3f604216633900d6d5896c27260e8711adcb\","
         << "\"expected_gbt1_sha256\":\"5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae\","
         << "\"phase1_core_linked\":true"
         << "}";
    return json.str();
}
}  // namespace

extern "C" JNIEXPORT jstring JNICALL
Java_ai_zer0pa_polymath_lab_bridge_NativePhase1Bridge_nativeEngineInfo(
    JNIEnv* env,
    jobject,
    jstring app_files_dir
) {
    const std::string files_dir = jstring_to_string(env, app_files_dir);
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "native engine info requested");
    return to_jstring(env, engine_info_json(files_dir));
}

extern "C" JNIEXPORT jstring JNICALL
Java_ai_zer0pa_polymath_lab_bridge_NativePhase1Bridge_nativeProbe(
    JNIEnv* env,
    jobject,
    jstring app_files_dir,
    jstring report_output_path,
    jstring tokenizer_dir,
    jstring tokenizer_table_path,
    jstring batch_list_path,
    jstring qai1_path,
    jstring pqa1_output_path,
    jstring bpe_algorithm,
    jstring phase1_exec_path,
    jint worker_count,
    jint flags
) {
    const std::string files_dir = jstring_to_string(env, app_files_dir);
    const std::string report_path = jstring_to_string(env, report_output_path);
    const std::string tokenizer_dir_value = jstring_to_string(env, tokenizer_dir);
    const std::string tokenizer_table_value = jstring_to_string(env, tokenizer_table_path);
    const std::string batch_list_value = jstring_to_string(env, batch_list_path);
    const std::string qai1_value = jstring_to_string(env, qai1_path);
    const std::string pqa1_value = jstring_to_string(env, pqa1_output_path);
    const std::string bpe_algorithm_value = jstring_to_string(env, bpe_algorithm);
    const std::string phase1_exec_value = jstring_to_string(env, phase1_exec_path);
    phase1_engine_t* raw_engine = nullptr;
    const int create_result = phase1_engine_create(files_dir.c_str(), &raw_engine);
    std::unique_ptr<phase1_engine_t, EngineDeleter> engine(raw_engine);

    phase1_run_result_t result{};
    int run_result = 1;
    if (create_result == 0 && engine) {
        phase1_run_config_t config{};
        config.tokenizer_dir = tokenizer_dir_value.c_str();
        config.gbt1_path = tokenizer_table_value.c_str();
        config.batch_list_path = batch_list_value.c_str();
        config.qai1_path = qai1_value.c_str();
        config.pqa1_output_path = pqa1_value.c_str();
        config.report_output_path = report_path.c_str();
        config.bpe_algorithm = bpe_algorithm_value.empty() ? "heap" : bpe_algorithm_value.c_str();
        config.phase1_exec_path = phase1_exec_value.c_str();
        config.worker_count = worker_count > 0 ? static_cast<uint32_t>(worker_count) : 1U;
        config.flags = flags > 0 ? static_cast<uint32_t>(flags) : 0U;
        run_result = phase1_engine_run(engine.get(), &config, &result);
    }

    std::ostringstream json;
    json << "{"
         << "\"schema_version\":\"native_probe_result_v1\","
         << "\"return_code\":" << run_result << ","
         << "\"probe_state\":\"PROBE\","
         << "\"connection_state\":\"" << (run_result == 0 ? "CONNECTED" : "BLOCKED") << "\","
         << "\"gate_result\":\"" << (run_result == 0 ? "probe" : "blocked") << "\","
         << "\"phase1_core_linked\":true,"
         << "\"records\":" << result.records << ","
         << "\"token_ids\":" << result.token_ids << ","
         << "\"distinct_token_ids\":" << result.distinct_token_ids << ","
         << "\"vocab_size\":" << result.vocab_size << ","
         << "\"vocab_coverage_ratio\":" << result.vocab_coverage_ratio << ","
         << "\"tokens_per_record_mean\":" << result.tokens_per_record_mean << ","
         << "\"tokens_per_record_p50\":" << result.tokens_per_record_p50 << ","
         << "\"tokens_per_record_p95\":" << result.tokens_per_record_p95 << ","
         << "\"tokens_per_record_p99\":" << result.tokens_per_record_p99 << ","
         << "\"tokens_per_record_distribution_source\":\"pqa1_record_headers\","
         << "\"wall_sec\":" << result.wall_sec << ","
         << "\"input_bytes\":" << result.input_bytes << ","
         << "\"output_bytes\":" << result.output_bytes << ","
         << "\"input_mb_per_sec\":" << result.input_mb_per_sec << ","
         << "\"token_ids_per_sec\":" << result.token_ids_per_sec << ","
         << "\"records_per_sec\":" << result.records_per_sec << ","
         << "\"latency_ms_per_record\":" << result.latency_ms_per_record << ","
         << "\"latency_ms_per_prompt\":" << result.latency_ms_per_record << ","
         << "\"pss_kb\":" << result.pss_kb << ","
         << "\"rss_kb\":" << result.rss_kb << ","
         << "\"peak_rss_kb\":" << result.peak_rss_kb << ","
         << "\"cpuset_before\":\"" << json_escape(result.cpuset_before) << "\","
         << "\"cpuset_after\":\"" << json_escape(result.cpuset_after) << "\","
         << "\"cpus_allowed_list_before\":\"" << json_escape(result.cpus_allowed_list_before) << "\","
         << "\"cpus_allowed_list_after\":\"" << json_escape(result.cpus_allowed_list_after) << "\","
         << "\"job_count\":" << result.job_count << ","
         << "\"thread_count\":" << result.thread_count << ","
         << "\"flags\":" << (flags > 0 ? flags : 0) << ","
         << "\"hot_loop_allocations\":" << result.hot_loop_allocations << ","
         << "\"span_errors\":" << result.span_errors << ","
         << "\"parity_mismatches\":" << result.parity_mismatches << ","
         << "\"parity_state\":\"not_checked_in_apk_run\","
         << "\"bpe_algorithm\":\"" << json_escape(bpe_algorithm_value.empty() ? "heap" : bpe_algorithm_value) << "\","
         << "\"run_interface\":\"" << (batch_list_value.empty() ? "single-input" : "batch-list") << "\","
         << "\"report_output_path\":\"" << json_escape(report_path) << "\","
         << "\"batch_list_path\":\"" << json_escape(batch_list_value) << "\","
         << "\"qai1_path\":\"" << json_escape(qai1_value) << "\","
         << "\"pqa1_output_path\":\"" << json_escape(pqa1_value) << "\","
         << "\"phase1_exec_path\":\"" << json_escape(phase1_exec_value) << "\","
         << "\"error_message\":\"" << json_escape(result.error_message) << "\""
         << "}";
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "native probe return_code=%d records=%llu token_ids=%llu",
                        run_result,
                        static_cast<unsigned long long>(result.records),
                        static_cast<unsigned long long>(result.token_ids));
    return to_jstring(env, json.str());
}
