#if defined(__ANDROID__)
#define _GNU_SOURCE 1
#endif

#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#endif
#define _POSIX_C_SOURCE 200809L

#include "cur0s_sha256.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#if defined(__ANDROID__) || defined(__linux__)
#include <sys/sysmacros.h>
#endif

extern char **environ;

#if defined(__ANDROID__)
#include <linux/memfd.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#endif

#if !defined(__ANDROID__) \
    && defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
#ifndef AT_EMPTY_PATH
#define AT_EMPTY_PATH 0x1000
#endif
#ifndef F_ADD_SEALS
#define F_ADD_SEALS 1033
#endif
#ifndef F_GET_SEALS
#define F_GET_SEALS 1034
#endif
#ifndef F_SEAL_SEAL
#define F_SEAL_SEAL 0x0001
#endif
#ifndef F_SEAL_SHRINK
#define F_SEAL_SHRINK 0x0002
#endif
#ifndef F_SEAL_GROW
#define F_SEAL_GROW 0x0004
#endif
#ifndef F_SEAL_WRITE
#define F_SEAL_WRITE 0x0008
#endif
#ifndef MFD_CLOEXEC
#define MFD_CLOEXEC 0x0001U
#endif
#ifndef MFD_ALLOW_SEALING
#define MFD_ALLOW_SEALING 0x0002U
#endif
static int cur0s_test_memfd_create(const char *name, unsigned int flags) {
    (void)name;
    (void)flags;
    errno = ENOSYS;
    return -1;
}
static int cur0s_platform_execveat(
    int descriptor,
    const char *path,
    char *const arguments[],
    char *const environment[],
    int flags
) {
    (void)descriptor;
    (void)path;
    (void)arguments;
    (void)environment;
    (void)flags;
    errno = ENOSYS;
    return -1;
}
#define memfd_create cur0s_test_memfd_create
#define CUR0S_COMPILE_ANDROID_LAUNCH 1
#elif defined(__ANDROID__)
#ifndef __NR_execveat
#error "CUR0S native preflight requires the Android execveat syscall number"
#endif
static int cur0s_platform_execveat(
    int descriptor,
    const char *path,
    char *const arguments[],
    char *const environment[],
    int flags
) {
    return (int)syscall(
        __NR_execveat,
        descriptor,
        path,
        arguments,
        environment,
        flags
    );
}
#define CUR0S_COMPILE_ANDROID_LAUNCH 1
#endif

#ifndef O_CLOEXEC
#error "CUR0S native preflight requires O_CLOEXEC"
#endif
#ifndef O_NOFOLLOW
#error "CUR0S native preflight requires O_NOFOLLOW"
#endif
#ifndef AT_SYMLINK_NOFOLLOW
#error "CUR0S native preflight requires AT_SYMLINK_NOFOLLOW"
#endif
#if defined(__ANDROID__) && !defined(O_PATH)
#error "CUR0S native preflight requires O_PATH for Android ancestor traversal"
#endif

#define MAX_MANIFEST_BYTES (4U * 1024U * 1024U)
#define MAX_MANIFEST_ENTRIES 4096U
#define MAX_ABSOLUTE_PATH_BYTES 8192U
#define MAX_RELATIVE_PATH_BYTES 65536U
#define MAX_TREE_ENTRIES 200000U
#define MAX_SYMLINK_TARGET_BYTES 65536U
#define MAX_PATH_COMPONENTS 128U
#define MAX_TREE_DEPTH 128U
#define MAX_ATTESTATION_BYTES (1024U * 1024U)
#define HASH_READ_BYTES (1024U * 1024U)
#define MAX_NATIVE_MAP_BYTES (2U * 1024U * 1024U)
#define MAX_NATIVE_MAP_RECORDS 16U

#define RUNNER_DESCRIPTOR 3
#define ATTESTATION_DESCRIPTOR 4
#define MANIFEST_DESCRIPTOR 5
#define PREREGISTRATION_DESCRIPTOR 6
#define AMBIENT_DESCRIPTOR_MINIMUM 8
#define RELOCATED_DESCRIPTOR_MINIMUM 16

#define MANIFEST_HEADER "CUR0S_NATIVE_PREFLIGHT_MANIFEST_V3"
#define TREE_CANONICALIZATION \
    "sorted_relative_POSIX_paths_canonical_JSON_type_mode_" \
    "regular_bytes_sha256_source_only_excluding_root_site_packages_" \
    "all_pycache_and_pyc_reject_external_symlinks_root_excluded"

/*
 * Strict UTF-8/LF manifest grammar (one record per line, tabs as separators):
 *
 * CUR0S_NATIVE_PREFLIGHT_MANIFEST_V3
 * FILE <absolute-path> <mode> <uid> <gid> <nlink> <bytes> <sha256:hex>
 * FILE <absolute-path> <mode> <uid> <gid> <nlink> <bytes> <sha256:hex>
 *      <native-self|python|runner|preregistration>
 * Native-self FILE appends <executable-map-offset> <executable-mapped-bytes>.
 * SYMLINK <absolute-path> <mode> <uid> <gid> <nlink> <literal-target>
 * STDLIB_TREE <absolute-path> <mode> <uid> <gid> <nlink> <entry-count>
 *             <regular-bytes> <sha256:hex> <TREE_CANONICALIZATION>
 * EXEC_PLAN <run-id> <action-path> <output-path> <python-argv0>
 *           <-IBS> <-X> <run-scoped-absent-pycache-prefix>
 *           <child-environment-sha256>
 *           <outer-environment-sha256> <3> <4> <5> <6>
 *
 * The caller supplies the manifest's own SHA-256 separately. Paths, integers,
 * modes, field counts, hash spelling, and the final newline are canonical.
 */

/*
 * This verifier makes two complete observations and binds open descriptors to
 * directory entries. That closes accidental mutation and observed pathname
 * replacement races. No finite user-space checker can prove that a hostile
 * process with the same UID did not replace and restore state entirely between
 * observations. Every machine-readable result states this ceiling explicitly.
 */
#define SECURITY_CEILING \
    "observational_only_no_guarantee_against_a_concurrent_malicious_" \
    "same_uid_between_checks"

#define PYTHON_COMBINED_FLAGS "-IBS"
#define PYTHON_XOPTION_FLAG "-X"
#define PYTHON_PYCACHE_SUFFIX "/python_pycache_forbidden"
#define EXPECTED_PYTHON_ARGV0 "/data/data/com.termux/files/usr/bin/python"
#define EXPECTED_ACTION_ROOT \
    "/data/data/com.termux/files/home/polymath_gemma4_e4b_frontier/"
#define EXPECTED_OUTPUT_SUFFIX "/candidate_runs/candidate-001"
#define RUN_ID_SUFFIX "_cur0s_commercial_sources_v1"

/*
 * This exact canonical JSON object is the complete child environment.  The
 * EXEC_PLAN binds its SHA-256, and production launch supplies no inherited
 * environment entries.  The FD declarations are authority inputs, not claims
 * that Python has already checked them.
 */
#define LAUNCH_ENVIRONMENT_JSON \
    "{\"ANDROID_ROOT\":\"/system\"," \
    "\"CUR0S_NATIVE_ATTESTATION_FD\":\"4\"," \
    "\"CUR0S_NATIVE_MANIFEST_FD\":\"5\"," \
    "\"CUR0S_PREREGISTRATION_FD\":\"6\"," \
    "\"HOME\":\"/data/data/com.termux/files/home\"," \
    "\"LC_ALL\":\"C\"," \
    "\"LD_PRELOAD\":\"/data/data/com.termux/files/usr/lib/libtermux-exec.so\"," \
    "\"PATH\":\"/data/data/com.termux/files/usr/bin:/system/bin\"," \
    "\"TERMUX_EXEC__PROC_SELF_EXE\":\"/data/data/com.termux/files/usr/bin/python\"}"

/*
 * Production is invoked through `/system/bin/env -i`; therefore this exact
 * empty canonical JSON object is the complete native process environment.
 * The manifest binds its digest independently from the child Python
 * environment above.
 */
#define OUTER_ENVIRONMENT_JSON "{}"

#ifndef CUR0S_AMBIENT_DESCRIPTOR_DIRECTORY
#if defined(__ANDROID__) || defined(__linux__)
#define CUR0S_AMBIENT_DESCRIPTOR_DIRECTORY "/proc/self/fd"
#else
#define CUR0S_AMBIENT_DESCRIPTOR_DIRECTORY "/dev/fd"
#endif
#endif

#ifndef CUR0S_NATIVE_MAPS_PATH
#define CUR0S_NATIVE_MAPS_PATH "/proc/self/maps"
#endif

typedef enum {
    ENTRY_FILE = 1,
    ENTRY_STDLIB_TREE = 2,
    ENTRY_SYMLINK = 3,
} entry_type;

typedef struct {
    entry_type type;
    char *path;
    uint32_t mode;
    uint64_t uid;
    uint64_t gid;
    uint64_t nlink;
    uint64_t bytes;
    uint64_t entry_count;
    uint64_t executable_map_offset;
    uint64_t executable_map_mapped_bytes;
    int executable_map_geometry_present;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    char *role;
    char *target;
} manifest_entry;

typedef struct {
    int present;
    char *run_id;
    char *action_path;
    char *output_path;
    char *python_argv0;
    char *pycache_prefix;
    uint8_t child_environment_digest[CUR0S_SHA256_DIGEST_BYTES];
    uint8_t outer_environment_digest[CUR0S_SHA256_DIGEST_BYTES];
} execution_plan;

typedef struct {
    uint64_t device_major;
    uint64_t device_minor;
    uint64_t inode;
    uint64_t mapped_bytes;
    uint64_t offset;
    char path[MAX_ABSOLUTE_PATH_BYTES + 1U];
    char permissions[5];
    char runtime_role[32];
} native_map_record;

typedef struct {
    native_map_record records[MAX_NATIVE_MAP_RECORDS];
    size_t count;
    int production_policy_enforced;
    int vvar_present;
} native_map_snapshot;

typedef struct {
    manifest_entry *entries;
    size_t count;
    size_t capacity;
    execution_plan plan;
} manifest;

typedef enum {
    MODE_VERIFY_ONLY = 1,
    MODE_LAUNCH = 2,
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    MODE_TEST_LAUNCH_PLAN = 3,
#endif
} operation_mode;

typedef struct {
    operation_mode mode;
    const char *manifest_path;
    uint8_t manifest_digest[CUR0S_SHA256_DIGEST_BYTES];
    uint8_t expected_preregistration_digest[CUR0S_SHA256_DIGEST_BYTES];
    int expected_preregistration_digest_present;
    uint8_t observed_outer_environment_digest[CUR0S_SHA256_DIGEST_BYTES];
    int outer_environment_observed;
} arguments_config;

typedef struct {
    dev_t device;
    ino_t inode;
    mode_t mode;
    nlink_t nlink;
    off_t size;
    uid_t uid;
    gid_t gid;
    int64_t mtime_seconds;
    long mtime_nanoseconds;
    int64_t ctime_seconds;
    long ctime_nanoseconds;
} stat_identity;

typedef struct {
    stat_identity identity;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    uint64_t bytes;
    uint64_t entry_count;
} observation;

typedef enum {
    RECORD_DIRECTORY = 1,
    RECORD_REGULAR = 2,
    RECORD_SYMLINK = 3,
} record_type;

typedef struct {
    record_type type;
    char *relative_path;
    char mode[5];
    uint64_t bytes;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    char *target;
} tree_record;

typedef struct {
    tree_record *records;
    size_t count;
    size_t capacity;
    uint64_t regular_bytes;
} tree_record_list;

typedef struct {
    char *data;
    size_t length;
    size_t capacity;
} text_buffer;

typedef struct {
    const manifest_entry *native_self;
    const manifest_entry *python;
    const manifest_entry *runner;
    const manifest_entry *preregistration;
    size_t native_self_index;
    size_t python_index;
    size_t runner_index;
    size_t preregistration_index;
} launch_roles;

typedef struct {
    int python_descriptor;
    int runner_descriptor;
    int manifest_descriptor;
    int preregistration_descriptor;
} held_launch_descriptors;

static const char *error_code = NULL;

static int reject(const char *code) {
    if (error_code == NULL) {
        error_code = code;
    }
    return -1;
}

static char *duplicate_string(const char *value) {
    size_t length = strlen(value);
    char *copy = malloc(length + 1U);

    if (copy == NULL) {
        reject("memory_allocation_failed");
        return NULL;
    }
    memcpy(copy, value, length + 1U);
    return copy;
}

static void free_text_buffer(text_buffer *value) {
    free(value->data);
    memset(value, 0, sizeof(*value));
}

static int reserve_text_buffer(text_buffer *value, size_t additional) {
    size_t required;
    size_t next_capacity;
    char *expanded;

    if (additional > MAX_ATTESTATION_BYTES
        || value->length > MAX_ATTESTATION_BYTES - additional) {
        return reject("native_attestation_size_limit_exceeded");
    }
    required = value->length + additional + 1U;
    if (required <= value->capacity) {
        return 0;
    }
    next_capacity = value->capacity == 0U ? 1024U : value->capacity;
    while (next_capacity < required) {
        if (next_capacity > (MAX_ATTESTATION_BYTES + 1U) / 2U) {
            next_capacity = MAX_ATTESTATION_BYTES + 1U;
            break;
        }
        next_capacity *= 2U;
    }
    if (next_capacity < required) {
        return reject("native_attestation_size_limit_exceeded");
    }
    expanded = realloc(value->data, next_capacity);
    if (expanded == NULL) {
        return reject("memory_allocation_failed");
    }
    value->data = expanded;
    value->capacity = next_capacity;
    return 0;
}

static int append_text_bytes(text_buffer *value, const char *payload, size_t bytes) {
    if (reserve_text_buffer(value, bytes) != 0) {
        return -1;
    }
    memcpy(value->data + value->length, payload, bytes);
    value->length += bytes;
    value->data[value->length] = '\0';
    return 0;
}

static int append_text(text_buffer *value, const char *payload) {
    return append_text_bytes(value, payload, strlen(payload));
}

static int append_u64(text_buffer *value, uint64_t number) {
    char decimal[32];
    int printed = snprintf(decimal, sizeof(decimal), "%" PRIu64, number);

    if (printed <= 0 || (size_t)printed >= sizeof(decimal)) {
        return reject("native_attestation_integer_format_failed");
    }
    return append_text_bytes(value, decimal, (size_t)printed);
}

static int append_json_string_value(text_buffer *value, const char *payload) {
    static const char hex_digits[] = "0123456789abcdef";
    const uint8_t *cursor = (const uint8_t *)payload;

    if (append_text(value, "\"") != 0) {
        return -1;
    }
    while (*cursor != 0U) {
        char escaped[6];
        const char *short_escape = NULL;

        switch (*cursor) {
            case '"':
                short_escape = "\\\"";
                break;
            case '\\':
                short_escape = "\\\\";
                break;
            case '\b':
                short_escape = "\\b";
                break;
            case '\f':
                short_escape = "\\f";
                break;
            case '\n':
                short_escape = "\\n";
                break;
            case '\r':
                short_escape = "\\r";
                break;
            case '\t':
                short_escape = "\\t";
                break;
            default:
                break;
        }
        if (short_escape != NULL) {
            if (append_text(value, short_escape) != 0) {
                return -1;
            }
        } else if (*cursor < 0x20U) {
            escaped[0] = '\\';
            escaped[1] = 'u';
            escaped[2] = '0';
            escaped[3] = '0';
            escaped[4] = hex_digits[*cursor >> 4U];
            escaped[5] = hex_digits[*cursor & 0x0fU];
            if (append_text_bytes(value, escaped, sizeof(escaped)) != 0) {
                return -1;
            }
        } else if (append_text_bytes(value, (const char *)cursor, 1U) != 0) {
            return -1;
        }
        ++cursor;
    }
    return append_text(value, "\"");
}

static int valid_utf8(const char *value) {
    const uint8_t *cursor = (const uint8_t *)value;

    while (*cursor != 0U) {
        uint32_t codepoint;
        size_t continuation_bytes;

        if (*cursor < 0x80U) {
            ++cursor;
            continue;
        }
        if ((*cursor & 0xe0U) == 0xc0U) {
            codepoint = (uint32_t)(*cursor & 0x1fU);
            continuation_bytes = 1U;
            if (codepoint < 2U) {
                return 0;
            }
        } else if ((*cursor & 0xf0U) == 0xe0U) {
            codepoint = (uint32_t)(*cursor & 0x0fU);
            continuation_bytes = 2U;
        } else if ((*cursor & 0xf8U) == 0xf0U) {
            codepoint = (uint32_t)(*cursor & 0x07U);
            continuation_bytes = 3U;
        } else {
            return 0;
        }
        ++cursor;
        for (size_t index = 0; index < continuation_bytes; ++index) {
            if ((cursor[index] & 0xc0U) != 0x80U) {
                return 0;
            }
            codepoint = (codepoint << 6U) | (uint32_t)(cursor[index] & 0x3fU);
        }
        if ((continuation_bytes == 2U && codepoint < 0x800U)
            || (continuation_bytes == 3U && codepoint < 0x10000U)
            || (codepoint >= 0xd800U && codepoint <= 0xdfffU)
            || codepoint > 0x10ffffU) {
            return 0;
        }
        cursor += continuation_bytes;
    }
    return 1;
}

static int canonical_absolute_path(const char *path) {
    const char *cursor;
    size_t length;
    size_t components = 0U;

    if (path == NULL || path[0] != '/') {
        return 0;
    }
    length = strlen(path);
    if (length < 2U || length > MAX_ABSOLUTE_PATH_BYTES || path[length - 1U] == '/') {
        return 0;
    }
    if (!valid_utf8(path)) {
        return 0;
    }
    cursor = path + 1;
    while (*cursor != '\0') {
        const char *separator = strchr(cursor, '/');
        size_t component_bytes = separator == NULL
            ? strlen(cursor)
            : (size_t)(separator - cursor);

        if (component_bytes == 0U
            || (component_bytes == 1U && cursor[0] == '.')
            || (component_bytes == 2U && cursor[0] == '.' && cursor[1] == '.')) {
            return 0;
        }
        if (memchr(cursor, '\t', component_bytes) != NULL
            || memchr(cursor, '\n', component_bytes) != NULL
            || memchr(cursor, '\r', component_bytes) != NULL) {
            return 0;
        }
        if (separator == NULL) {
            break;
        }
        ++components;
        if (components >= MAX_PATH_COMPONENTS) {
            return 0;
        }
        cursor = separator + 1;
    }
    return components < MAX_PATH_COMPONENTS;
}

static int canonical_manifest_text(const char *value, size_t maximum_bytes) {
    size_t bytes;

    if (value == NULL || value[0] == '\0' || !valid_utf8(value)) {
        return 0;
    }
    bytes = strlen(value);
    return bytes <= maximum_bytes
        && strchr(value, '\t') == NULL
        && strchr(value, '\n') == NULL
        && strchr(value, '\r') == NULL;
}

static int ancestor_directory_open_flags(void) {
#if defined(__ANDROID__)
    return O_PATH | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW;
#else
    return O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW;
#endif
}

static int open_absolute_nofollow(const char *path, int final_directory) {
    int current_fd;
    const char *cursor;

    if (!canonical_absolute_path(path)) {
        reject("path_not_canonical_absolute_utf8");
        return -1;
    }
    current_fd = open("/", ancestor_directory_open_flags());
    if (current_fd < 0) {
        reject("root_directory_open_failed");
        return -1;
    }
    cursor = path + 1;
    while (*cursor != '\0') {
        const char *separator = strchr(cursor, '/');
        size_t component_bytes = separator == NULL
            ? strlen(cursor)
            : (size_t)(separator - cursor);
        int is_final = separator == NULL;
        int flags = is_final
            ? O_RDONLY | O_CLOEXEC | O_NOFOLLOW
            : ancestor_directory_open_flags();
        char *component = malloc(component_bytes + 1U);
        int next_fd;

        if (component == NULL) {
            close(current_fd);
            reject("memory_allocation_failed");
            return -1;
        }
        memcpy(component, cursor, component_bytes);
        component[component_bytes] = '\0';
        if (!is_final || final_directory) {
            flags |= O_DIRECTORY;
        }
        next_fd = openat(current_fd, component, flags);
        free(component);
        if (next_fd < 0) {
            close(current_fd);
            reject("secure_path_component_open_failed");
            return -1;
        }
        if (close(current_fd) != 0) {
            close(next_fd);
            reject("path_descriptor_close_failed");
            return -1;
        }
        current_fd = next_fd;
        if (is_final) {
            break;
        }
        cursor = separator + 1;
    }
    return current_fd;
}

static int open_absolute_parent_nofollow(
    const char *path,
    int *parent_descriptor,
    char **leaf_name
) {
    const char *separator;
    char *parent_path;
    char *leaf;
    size_t parent_bytes;
    int descriptor;

    if (!canonical_absolute_path(path)) {
        return reject("path_not_canonical_absolute_utf8");
    }
    separator = strrchr(path, '/');
    if (separator == NULL || separator[1] == '\0') {
        return reject("path_leaf_invalid");
    }
    leaf = duplicate_string(separator + 1);
    if (leaf == NULL) {
        return -1;
    }
    parent_bytes = (size_t)(separator - path);
    if (parent_bytes == 0U) {
        parent_path = duplicate_string("/");
    } else {
        parent_path = malloc(parent_bytes + 1U);
        if (parent_path != NULL) {
            memcpy(parent_path, path, parent_bytes);
            parent_path[parent_bytes] = '\0';
        }
    }
    if (parent_path == NULL) {
        free(leaf);
        return reject("memory_allocation_failed");
    }
    if (strcmp(parent_path, "/") == 0) {
        descriptor = open(
            "/",
            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW
        );
        if (descriptor < 0) {
            reject("root_directory_open_failed");
        }
    } else {
        descriptor = open_absolute_nofollow(parent_path, 1);
    }
    free(parent_path);
    if (descriptor < 0) {
        free(leaf);
        return -1;
    }
    *parent_descriptor = descriptor;
    *leaf_name = leaf;
    return 0;
}

static int require_path_absent(const char *path) {
    struct stat information;
    int parent_descriptor = -1;
    char *leaf = NULL;
    int status = -1;

    if (open_absolute_parent_nofollow(path, &parent_descriptor, &leaf) != 0) {
        return -1;
    }
    errno = 0;
    if (fstatat(
            parent_descriptor,
            leaf,
            &information,
            AT_SYMLINK_NOFOLLOW
        ) == 0) {
        reject("python_pycache_prefix_must_be_absent");
        goto cleanup;
    }
    if (errno != ENOENT) {
        reject("python_pycache_prefix_absence_check_failed");
        goto cleanup;
    }
    status = 0;

cleanup:
    free(leaf);
    if (close(parent_descriptor) != 0 && status == 0) {
        return reject("python_pycache_parent_close_failed");
    }
    return status;
}

static const char *native_map_runtime_role(
    const char *path,
    const char *native_self_path
) {
    if (strcmp(path, native_self_path) == 0) {
        return "native-self";
    }
    if (strcmp(path, "/apex/com.android.runtime/bin/linker64") == 0) {
        return "android_linker64";
    }
    if (strcmp(
            path,
            "/apex/com.android.runtime/lib64/bionic/libc.so"
        ) == 0) {
        return "android_bionic_libc";
    }
    if (strcmp(
            path,
            "/apex/com.android.runtime/lib64/bionic/libdl.so"
        ) == 0) {
        return "android_bionic_libdl";
    }
    if (strcmp(
            path,
            "/apex/com.android.runtime/lib64/bionic/libm.so"
        ) == 0) {
        return "android_bionic_libm";
    }
    if (strcmp(path, "/system/lib64/libc++.so") == 0) {
        return "system_libcxx";
    }
    if (strcmp(path, "/system/lib64/libnetd_client.so") == 0) {
        return "system_libnetd_client";
    }
    if (strcmp(path, "[vdso]") == 0) {
        return "kernel_vdso";
    }
    if (strcmp(path, "[vvar]") == 0) {
        return "kernel_vvar";
    }
    return NULL;
}

static int native_map_shape_admitted(
    const char *runtime_role,
    uint64_t offset,
    uint64_t mapped_bytes
) {
    if (strcmp(runtime_role, "native-self") == 0) {
        return offset % 4096U == 0U && mapped_bytes > 0U
            && mapped_bytes % 4096U == 0U;
    }
    if (strcmp(runtime_role, "android_linker64") == 0) {
        return offset == 0x4c000U && mapped_bytes == 0x116000U;
    }
    if (strcmp(runtime_role, "android_bionic_libc") == 0) {
        return offset == 0x48000U && mapped_bytes == 0x8f000U;
    }
    if (strcmp(runtime_role, "android_bionic_libdl") == 0) {
        return offset == 0x4000U && mapped_bytes == 0x1000U;
    }
    if (strcmp(runtime_role, "android_bionic_libm") == 0) {
        return offset == 0x14000U && mapped_bytes == 0x24000U;
    }
    if (strcmp(runtime_role, "system_libcxx") == 0) {
        return offset == 0x84000U && mapped_bytes == 0x7b000U;
    }
    if (strcmp(runtime_role, "system_libnetd_client") == 0) {
        return offset == 0x4000U && mapped_bytes == 0x4000U;
    }
    if (strcmp(runtime_role, "kernel_vdso") == 0) {
        return offset == 0U && mapped_bytes == 0x1000U;
    }
    if (strcmp(runtime_role, "kernel_vvar") == 0) {
        return offset == 0U && mapped_bytes == 0x2000U;
    }
    return 0;
}

static int compare_native_map_records(const void *left_value, const void *right_value) {
    const native_map_record *left = left_value;
    const native_map_record *right = right_value;
    int path_order = strcmp(left->path, right->path);
    int permission_order;

    if (path_order != 0) {
        return path_order;
    }
    if (left->offset < right->offset) {
        return -1;
    }
    if (left->offset > right->offset) {
        return 1;
    }
    permission_order = strcmp(left->permissions, right->permissions);
    if (permission_order != 0) {
        return permission_order;
    }
    if (left->inode < right->inode) {
        return -1;
    }
    return left->inode > right->inode ? 1 : 0;
}

static int append_captured_native_map(
    native_map_snapshot *snapshot,
    const char *path,
    const char *permissions,
    const char *runtime_role,
    uint64_t mapped_bytes,
    uint64_t offset,
    uint64_t device_major,
    uint64_t device_minor,
    uint64_t inode
) {
    native_map_record *record;
    size_t path_bytes = strlen(path);
    size_t role_bytes = strlen(runtime_role);

    if (snapshot->count >= MAX_NATIVE_MAP_RECORDS
        || path_bytes == 0U || path_bytes > MAX_ABSOLUTE_PATH_BYTES
        || role_bytes == 0U || role_bytes >= sizeof(record->runtime_role)) {
        return reject("earliest_native_maps_record_limit_exceeded");
    }
    record = &snapshot->records[snapshot->count++];
    memset(record, 0, sizeof(*record));
    memcpy(record->path, path, path_bytes + 1U);
    memcpy(record->permissions, permissions, 5U);
    memcpy(record->runtime_role, runtime_role, role_bytes + 1U);
    record->offset = offset;
    record->mapped_bytes = mapped_bytes;
    record->device_major = device_major;
    record->device_minor = device_minor;
    record->inode = inode;
    return 0;
}

static int capture_earliest_native_maps(
    int argument_count,
    char **arguments,
    native_map_snapshot *snapshot
) {
    memset(snapshot, 0, sizeof(*snapshot));
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    (void)argument_count;
    (void)arguments;
    (void)&native_map_runtime_role;
    (void)&native_map_shape_admitted;
    (void)&compare_native_map_records;
    (void)&append_captured_native_map;
    snapshot->production_policy_enforced = 0;
    return 0;
#else
    uint8_t *payload = NULL;
    size_t payload_bytes = 0U;
    int descriptor = -1;
    char *line;
    size_t required_native_self = 0U;
    size_t required_linker = 0U;
    size_t required_libc = 0U;
    size_t required_libdl = 0U;
    size_t required_libm = 0U;
    size_t required_libcxx = 0U;
    size_t required_libnetd_client = 0U;
    size_t required_vdso = 0U;
    int status = -1;

    if (argument_count < 1 || arguments == NULL || arguments[0] == NULL
        || !canonical_absolute_path(arguments[0])) {
        return reject("earliest_native_maps_argv0_invalid");
    }
    descriptor = open(
        CUR0S_NATIVE_MAPS_PATH,
        O_RDONLY | O_CLOEXEC | O_NOFOLLOW
    );
    payload = malloc(MAX_NATIVE_MAP_BYTES + 1U);
    if (descriptor < 0 || payload == NULL) {
        reject("earliest_native_maps_open_or_allocate_failed");
        goto cleanup;
    }
    for (;;) {
        ssize_t received = read(
            descriptor,
            payload + payload_bytes,
            MAX_NATIVE_MAP_BYTES + 1U - payload_bytes
        );

        if (received < 0 && errno == EINTR) {
            continue;
        }
        if (received < 0) {
            reject("earliest_native_maps_read_failed");
            goto cleanup;
        }
        if (received == 0) {
            break;
        }
        payload_bytes += (size_t)received;
        if (payload_bytes > MAX_NATIVE_MAP_BYTES) {
            reject("earliest_native_maps_oversize");
            goto cleanup;
        }
    }
    if (payload_bytes == 0U || payload[payload_bytes - 1U] != '\n'
        || memchr(payload, '\0', payload_bytes) != NULL
        || memchr(payload, '\r', payload_bytes) != NULL) {
        reject("earliest_native_maps_framing_invalid");
        goto cleanup;
    }
    payload[payload_bytes] = '\0';
    line = (char *)payload;
    while (*line != '\0') {
        char *next = strchr(line, '\n');
        uint64_t start;
        uint64_t end;
        uint64_t offset;
        uint64_t inode;
        unsigned int device_major;
        unsigned int device_minor;
        char permissions[5] = {0};
        int consumed = 0;
        int parsed;
        char *path;
        const char *runtime_role;
        int executable;

        if (next == NULL || next == line) {
            reject("earliest_native_maps_record_invalid");
            goto cleanup;
        }
        *next = '\0';
        parsed = sscanf(
            line,
            "%" SCNx64 "-%" SCNx64 " %4s %" SCNx64
            " %x:%x %" SCNu64 "%n",
            &start,
            &end,
            permissions,
            &offset,
            &device_major,
            &device_minor,
            &inode,
            &consumed
        );
        if (parsed != 7 || consumed <= 0 || start >= end
            || strlen(permissions) != 4U
            || (permissions[0] != 'r' && permissions[0] != '-')
            || (permissions[1] != 'w' && permissions[1] != '-')
            || (permissions[2] != 'x' && permissions[2] != '-')
            || (permissions[3] != 'p' && permissions[3] != 's')) {
            reject("earliest_native_maps_record_invalid");
            goto cleanup;
        }
        path = line + (size_t)consumed;
        while (*path == ' ' || *path == '\t') {
            ++path;
        }
        executable = permissions[2] == 'x';
        runtime_role = native_map_runtime_role(path, arguments[0]);
        if (executable) {
            if (runtime_role == NULL || strcmp(permissions, "r-xp") != 0
                || strstr(path, " (deleted)") != NULL) {
                reject("earliest_native_maps_unexpected_executable_mapping");
                goto cleanup;
            }
        } else if (strcmp(path, "[vvar]") == 0) {
            if (strcmp(permissions, "r--p") != 0 || snapshot->vvar_present) {
                reject("earliest_native_maps_vvar_invalid");
                goto cleanup;
            }
            snapshot->vvar_present = 1;
        } else {
            line = next + 1;
            continue;
        }
        if (append_captured_native_map(
                snapshot,
                path,
                permissions,
                runtime_role,
                end - start,
                offset,
                (uint64_t)device_major,
                (uint64_t)device_minor,
                inode
            ) != 0) {
            goto cleanup;
        }
        if (!native_map_shape_admitted(runtime_role, offset, end - start)) {
            reject("earliest_native_maps_mapping_shape_mismatch");
            goto cleanup;
        }
        if (strcmp(runtime_role, "native-self") == 0) {
            ++required_native_self;
        } else if (strcmp(runtime_role, "android_linker64") == 0) {
            ++required_linker;
        } else if (strcmp(runtime_role, "android_bionic_libc") == 0) {
            ++required_libc;
        } else if (strcmp(runtime_role, "android_bionic_libdl") == 0) {
            ++required_libdl;
        } else if (strcmp(runtime_role, "android_bionic_libm") == 0) {
            ++required_libm;
        } else if (strcmp(runtime_role, "system_libcxx") == 0) {
            ++required_libcxx;
        } else if (strcmp(runtime_role, "system_libnetd_client") == 0) {
            ++required_libnetd_client;
        } else if (strcmp(runtime_role, "kernel_vdso") == 0) {
            ++required_vdso;
        }
        line = next + 1;
    }
    if (required_native_self != 1U || required_linker != 1U
        || required_libc != 1U || required_libdl != 1U
        || required_libm != 1U || required_libcxx != 1U
        || required_libnetd_client != 1U || required_vdso != 1U
        || !snapshot->vvar_present || snapshot->count != 9U) {
        reject("earliest_native_maps_required_mapping_missing");
        goto cleanup;
    }
    qsort(
        snapshot->records,
        snapshot->count,
        sizeof(snapshot->records[0]),
        compare_native_map_records
    );
    snapshot->production_policy_enforced = 1;
    status = 0;

cleanup:
    free(payload);
    if (descriptor >= 0 && close(descriptor) != 0 && status == 0) {
        return reject("earliest_native_maps_close_failed");
    }
    return status;
#endif
}

static stat_identity identity_from_stat(const struct stat *information) {
    stat_identity result;

    result.device = information->st_dev;
    result.inode = information->st_ino;
    result.mode = information->st_mode;
    result.nlink = information->st_nlink;
    result.size = information->st_size;
    result.uid = information->st_uid;
    result.gid = information->st_gid;
#if defined(__APPLE__)
    result.mtime_seconds = (int64_t)information->st_mtimespec.tv_sec;
    result.mtime_nanoseconds = information->st_mtimespec.tv_nsec;
    result.ctime_seconds = (int64_t)information->st_ctimespec.tv_sec;
    result.ctime_nanoseconds = information->st_ctimespec.tv_nsec;
#else
    result.mtime_seconds = (int64_t)information->st_mtim.tv_sec;
    result.mtime_nanoseconds = information->st_mtim.tv_nsec;
    result.ctime_seconds = (int64_t)information->st_ctim.tv_sec;
    result.ctime_nanoseconds = information->st_ctim.tv_nsec;
#endif
    return result;
}

static int identities_equal(const stat_identity *left, const stat_identity *right) {
    return left->device == right->device
        && left->inode == right->inode
        && left->mode == right->mode
        && left->nlink == right->nlink
        && left->size == right->size
        && left->uid == right->uid
        && left->gid == right->gid
        && left->mtime_seconds == right->mtime_seconds
        && left->mtime_nanoseconds == right->mtime_nanoseconds
        && left->ctime_seconds == right->ctime_seconds
        && left->ctime_nanoseconds == right->ctime_nanoseconds;
}

static int observations_equal(const observation *left, const observation *right) {
    return identities_equal(&left->identity, &right->identity)
        && left->bytes == right->bytes
        && left->entry_count == right->entry_count
        && memcmp(left->digest, right->digest, sizeof(left->digest)) == 0;
}

static int hash_open_descriptor(
    int descriptor,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES],
    uint64_t *byte_count
) {
    cur0s_sha256_context context;
    uint8_t *buffer = malloc(HASH_READ_BYTES);
    uint64_t total = 0U;

    if (buffer == NULL) {
        return reject("memory_allocation_failed");
    }
    if (lseek(descriptor, 0, SEEK_SET) < 0) {
        free(buffer);
        return reject("hash_target_seek_failed");
    }
    cur0s_sha256_init(&context);
    for (;;) {
        ssize_t received = read(descriptor, buffer, HASH_READ_BYTES);

        if (received < 0 && errno == EINTR) {
            continue;
        }
        if (received < 0) {
            free(buffer);
            return reject("hash_target_read_failed");
        }
        if (received == 0) {
            break;
        }
        if (UINT64_MAX - total < (uint64_t)received) {
            free(buffer);
            return reject("hash_target_size_overflow");
        }
        cur0s_sha256_update(&context, buffer, (size_t)received);
        total += (uint64_t)received;
    }
    free(buffer);
    cur0s_sha256_final(&context, digest);
    *byte_count = total;
    return 0;
}

static int reopen_identity_matches(
    const char *path,
    int directory,
    const stat_identity *expected
) {
    struct stat information;
    stat_identity observed;
    int descriptor = open_absolute_nofollow(path, directory);

    if (descriptor < 0) {
        return -1;
    }
    if (fstat(descriptor, &information) != 0) {
        close(descriptor);
        return reject("reopened_path_stat_failed");
    }
    observed = identity_from_stat(&information);
    if (close(descriptor) != 0) {
        return reject("reopened_path_close_failed");
    }
    if (!identities_equal(expected, &observed)) {
        return reject("directory_entry_replaced_during_observation");
    }
    return 0;
}

static int parse_sha256(
    const char *value,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES]
) {
    if (value == NULL || strncmp(value, "sha256:", 7U) != 0
        || strlen(value + 7U) != CUR0S_SHA256_HEX_BYTES) {
        return reject("sha256_format_invalid");
    }
    value += 7U;
    for (size_t index = 0; index < CUR0S_SHA256_DIGEST_BYTES; ++index) {
        unsigned int high;
        unsigned int low;
        char high_character = value[index * 2U];
        char low_character = value[(index * 2U) + 1U];

        if (high_character >= '0' && high_character <= '9') {
            high = (unsigned int)(high_character - '0');
        } else if (high_character >= 'a' && high_character <= 'f') {
            high = (unsigned int)(high_character - 'a') + 10U;
        } else {
            return reject("sha256_format_invalid");
        }
        if (low_character >= '0' && low_character <= '9') {
            low = (unsigned int)(low_character - '0');
        } else if (low_character >= 'a' && low_character <= 'f') {
            low = (unsigned int)(low_character - 'a') + 10U;
        } else {
            return reject("sha256_format_invalid");
        }
        digest[index] = (uint8_t)((high << 4U) | low);
    }
    return 0;
}

static int parse_decimal_u64(const char *value, uint64_t *result) {
    uint64_t parsed = 0U;

    if (value == NULL || value[0] == '\0'
        || (value[0] == '0' && value[1] != '\0')) {
        return reject("manifest_decimal_not_canonical");
    }
    for (const char *cursor = value; *cursor != '\0'; ++cursor) {
        unsigned int digit;

        if (*cursor < '0' || *cursor > '9') {
            return reject("manifest_decimal_not_canonical");
        }
        digit = (unsigned int)(*cursor - '0');
        if (parsed > (UINT64_MAX - digit) / 10U) {
            return reject("manifest_decimal_overflow");
        }
        parsed = (parsed * 10U) + digit;
    }
    *result = parsed;
    return 0;
}

static int parse_mode(const char *value, uint32_t *result) {
    uint32_t parsed = 0U;

    if (value == NULL || strlen(value) != 4U) {
        return reject("manifest_mode_invalid");
    }
    for (size_t index = 0; index < 4U; ++index) {
        if (value[index] < '0' || value[index] > '7') {
            return reject("manifest_mode_invalid");
        }
        parsed = (parsed << 3U) | (uint32_t)(value[index] - '0');
    }
    *result = parsed;
    return 0;
}

static void free_manifest(manifest *value) {
    for (size_t index = 0; index < value->count; ++index) {
        free(value->entries[index].path);
        free(value->entries[index].role);
        free(value->entries[index].target);
    }
    free(value->entries);
    free(value->plan.run_id);
    free(value->plan.action_path);
    free(value->plan.output_path);
    free(value->plan.python_argv0);
    free(value->plan.pycache_prefix);
    memset(value, 0, sizeof(*value));
}

static int append_manifest_entry(manifest *value, const manifest_entry *entry) {
    manifest_entry *expanded;
    size_t next_capacity;

    if (value->count >= MAX_MANIFEST_ENTRIES) {
        return reject("manifest_entry_limit_exceeded");
    }
    for (size_t index = 0; index < value->count; ++index) {
        if (strcmp(value->entries[index].path, entry->path) == 0) {
            return reject("manifest_duplicate_path");
        }
        if (entry->role != NULL && value->entries[index].role != NULL
            && strcmp(value->entries[index].role, entry->role) == 0) {
            return reject("manifest_duplicate_file_role");
        }
    }
    if (value->count == value->capacity) {
        next_capacity = value->capacity == 0U ? 8U : value->capacity * 2U;
        expanded = realloc(value->entries, next_capacity * sizeof(*expanded));
        if (expanded == NULL) {
            return reject("memory_allocation_failed");
        }
        value->entries = expanded;
        value->capacity = next_capacity;
    }
    memset(&value->entries[value->count], 0, sizeof(*value->entries));
    value->entries[value->count] = *entry;
    value->entries[value->count].path = duplicate_string(entry->path);
    value->entries[value->count].role = entry->role == NULL
        ? NULL
        : duplicate_string(entry->role);
    value->entries[value->count].target = entry->target == NULL
        ? NULL
        : duplicate_string(entry->target);
    if (value->entries[value->count].path == NULL
        || (entry->role != NULL && value->entries[value->count].role == NULL)
        || (entry->target != NULL && value->entries[value->count].target == NULL)) {
        free(value->entries[value->count].path);
        free(value->entries[value->count].role);
        free(value->entries[value->count].target);
        memset(&value->entries[value->count], 0, sizeof(*value->entries));
        return -1;
    }
    ++value->count;
    return 0;
}

static size_t split_tab_fields(char *line, char **fields, size_t capacity) {
    size_t count = 0U;
    char *cursor = line;

    while (count < capacity) {
        char *separator;

        fields[count++] = cursor;
        separator = strchr(cursor, '\t');
        if (separator == NULL) {
            return count;
        }
        *separator = '\0';
        cursor = separator + 1;
    }
    return strchr(cursor, '\t') == NULL ? count : capacity + 1U;
}

static int canonical_run_id(const char *value) {
    size_t suffix_bytes = strlen(RUN_ID_SUFFIX);
    size_t expected_bytes = 16U + suffix_bytes;

    if (value == NULL || strlen(value) != expected_bytes
        || value[8] != 'T' || value[15] != 'Z'
        || strcmp(value + 16U, RUN_ID_SUFFIX) != 0) {
        return 0;
    }
    for (size_t index = 0U; index < 16U; ++index) {
        if (index == 8U || index == 15U) {
            continue;
        }
        if (value[index] < '0' || value[index] > '9') {
            return 0;
        }
    }
    return 1;
}

static int valid_file_role(const char *value) {
    return value != NULL
        && (strcmp(value, "native-self") == 0
            || strcmp(value, "python") == 0
            || strcmp(value, "runner") == 0
            || strcmp(value, "preregistration") == 0);
}

static void digest_canonical_environment(
    const char *canonical_json,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES]
) {
    cur0s_sha256_context context;

    cur0s_sha256_init(&context);
    cur0s_sha256_update(
        &context,
        canonical_json,
        strlen(canonical_json)
    );
    cur0s_sha256_final(&context, digest);
}

static int digest_equals_canonical_environment(
    const uint8_t digest[CUR0S_SHA256_DIGEST_BYTES],
    const char *canonical_json
) {
    uint8_t expected[CUR0S_SHA256_DIGEST_BYTES];

    digest_canonical_environment(canonical_json, expected);
    return memcmp(expected, digest, sizeof(expected)) == 0;
}

static int observe_empty_outer_environment(arguments_config *config) {
    if (environ == NULL || environ[0] != NULL) {
        return reject("outer_environment_not_empty");
    }
    digest_canonical_environment(
        OUTER_ENVIRONMENT_JSON,
        config->observed_outer_environment_digest
    );
    config->outer_environment_observed = 1;
    return 0;
}

static int valid_plan_python_argv0(const char *value) {
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    return canonical_absolute_path(value);
#else
    return strcmp(value, EXPECTED_PYTHON_ARGV0) == 0;
#endif
}

static int assign_execution_plan(manifest *result, char **fields) {
    execution_plan plan = {0};
    size_t action_bytes;
    size_t output_bytes;
    char expected_action[MAX_ABSOLUTE_PATH_BYTES + 1U];
    char expected_output[MAX_ABSOLUTE_PATH_BYTES + 1U];
    char expected_pycache[MAX_ABSOLUTE_PATH_BYTES + 1U];
    int action_printed;
    int output_printed;
    int pycache_printed;

    if (result->plan.present) {
        return reject("manifest_duplicate_execution_plan");
    }
    if (!canonical_run_id(fields[1])
        || !canonical_absolute_path(fields[2])
        || !canonical_absolute_path(fields[3])
        || !canonical_absolute_path(fields[4])
        || !valid_plan_python_argv0(fields[4])
        || strcmp(fields[5], PYTHON_COMBINED_FLAGS) != 0
        || strcmp(fields[6], PYTHON_XOPTION_FLAG) != 0
        || !canonical_absolute_path(fields[7])
        || parse_sha256(fields[8], plan.child_environment_digest) != 0
        || !digest_equals_canonical_environment(
            plan.child_environment_digest,
            LAUNCH_ENVIRONMENT_JSON
        )
        || parse_sha256(fields[9], plan.outer_environment_digest) != 0
        || !digest_equals_canonical_environment(
            plan.outer_environment_digest,
            OUTER_ENVIRONMENT_JSON
        )
        || strcmp(fields[10], "3") != 0
        || strcmp(fields[11], "4") != 0
        || strcmp(fields[12], "5") != 0
        || strcmp(fields[13], "6") != 0) {
        return error_code == NULL
            ? reject("manifest_execution_plan_invalid")
            : -1;
    }
    action_printed = snprintf(
        expected_action,
        sizeof(expected_action),
        "%s%s",
        EXPECTED_ACTION_ROOT,
        fields[1]
    );
    if (action_printed <= 0 || (size_t)action_printed >= sizeof(expected_action)) {
        return reject("manifest_execution_action_path_oversize");
    }
    output_printed = snprintf(
        expected_output,
        sizeof(expected_output),
        "%s%s",
        expected_action,
        EXPECTED_OUTPUT_SUFFIX
    );
    if (output_printed <= 0 || (size_t)output_printed >= sizeof(expected_output)) {
        return reject("manifest_execution_output_path_oversize");
    }
    pycache_printed = snprintf(
        expected_pycache,
        sizeof(expected_pycache),
        "%s%s",
        expected_action,
        PYTHON_PYCACHE_SUFFIX
    );
    if (pycache_printed <= 0
        || (size_t)pycache_printed >= sizeof(expected_pycache)) {
        return reject("manifest_execution_pycache_path_oversize");
    }
    action_bytes = (size_t)action_printed;
    output_bytes = (size_t)output_printed;
    if (strlen(fields[2]) != action_bytes
        || memcmp(fields[2], expected_action, action_bytes + 1U) != 0
        || strlen(fields[3]) != output_bytes
        || memcmp(fields[3], expected_output, output_bytes + 1U) != 0
        || strcmp(fields[7], expected_pycache) != 0) {
        return reject("manifest_execution_paths_not_canonical_for_run");
    }
    plan.run_id = duplicate_string(fields[1]);
    plan.action_path = duplicate_string(fields[2]);
    plan.output_path = duplicate_string(fields[3]);
    plan.python_argv0 = duplicate_string(fields[4]);
    plan.pycache_prefix = duplicate_string(fields[7]);
    if (plan.run_id == NULL || plan.action_path == NULL
        || plan.output_path == NULL || plan.python_argv0 == NULL
        || plan.pycache_prefix == NULL) {
        free(plan.run_id);
        free(plan.action_path);
        free(plan.output_path);
        free(plan.python_argv0);
        free(plan.pycache_prefix);
        return -1;
    }
    plan.present = 1;
    result->plan = plan;
    return 0;
}

static int parse_manifest_payload(char *payload, size_t payload_bytes, manifest *result) {
    char *line;
    char *next_line;

    if (payload_bytes == 0U || payload[payload_bytes - 1U] != '\n'
        || memchr(payload, '\0', payload_bytes) != NULL
        || memchr(payload, '\r', payload_bytes) != NULL) {
        return reject("manifest_framing_invalid");
    }
    line = payload;
    next_line = strchr(line, '\n');
    if (next_line == NULL) {
        return reject("manifest_header_missing");
    }
    *next_line = '\0';
    if (strcmp(line, MANIFEST_HEADER) != 0) {
        return reject("manifest_header_mismatch");
    }
    line = next_line + 1;
    while (*line != '\0') {
        manifest_entry entry;
        char *fields[15];
        size_t field_count;

        next_line = strchr(line, '\n');
        if (next_line == NULL) {
            return reject("manifest_final_newline_missing");
        }
        *next_line = '\0';
        if (*line == '\0') {
            return reject("manifest_blank_line_rejected");
        }
        field_count = split_tab_fields(line, fields, 15U);
        memset(&entry, 0, sizeof(entry));
        if ((field_count == 8U || field_count == 9U || field_count == 11U)
            && strcmp(fields[0], "FILE") == 0) {
            entry.type = ENTRY_FILE;
            entry.path = fields[1];
            entry.role = field_count >= 9U ? fields[8] : NULL;
            if (!canonical_absolute_path(entry.path)
                || (entry.role != NULL && !valid_file_role(entry.role))
                || parse_mode(fields[2], &entry.mode) != 0
                || parse_decimal_u64(fields[3], &entry.uid) != 0
                || parse_decimal_u64(fields[4], &entry.gid) != 0
                || parse_decimal_u64(fields[5], &entry.nlink) != 0
                || parse_decimal_u64(fields[6], &entry.bytes) != 0
                || parse_sha256(fields[7], entry.digest) != 0) {
                return error_code == NULL
                    ? reject("manifest_file_entry_invalid")
                    : -1;
            }
            if (field_count == 11U) {
                if (strcmp(entry.role, "native-self") != 0
                    || parse_decimal_u64(
                        fields[9],
                        &entry.executable_map_offset
                    ) != 0
                    || parse_decimal_u64(
                        fields[10],
                        &entry.executable_map_mapped_bytes
                    ) != 0
                    || entry.executable_map_mapped_bytes == 0U) {
                    return reject("manifest_native_self_geometry_invalid");
                }
                entry.executable_map_geometry_present = 1;
            } else if (entry.role != NULL
                       && strcmp(entry.role, "native-self") == 0) {
                return reject("manifest_native_self_geometry_missing");
            }
        } else if (field_count == 7U
                   && strcmp(fields[0], "SYMLINK") == 0) {
            entry.type = ENTRY_SYMLINK;
            entry.path = fields[1];
            entry.target = fields[6];
            if (!canonical_absolute_path(entry.path)
                || parse_mode(fields[2], &entry.mode) != 0
                || parse_decimal_u64(fields[3], &entry.uid) != 0
                || parse_decimal_u64(fields[4], &entry.gid) != 0
                || parse_decimal_u64(fields[5], &entry.nlink) != 0
                || !canonical_manifest_text(
                    entry.target,
                    MAX_SYMLINK_TARGET_BYTES
                )) {
                return error_code == NULL
                    ? reject("manifest_symlink_entry_invalid")
                    : -1;
            }
        } else if (field_count == 10U
                   && strcmp(fields[0], "STDLIB_TREE") == 0) {
            entry.type = ENTRY_STDLIB_TREE;
            entry.path = fields[1];
            if (!canonical_absolute_path(entry.path)
                || parse_mode(fields[2], &entry.mode) != 0
                || parse_decimal_u64(fields[3], &entry.uid) != 0
                || parse_decimal_u64(fields[4], &entry.gid) != 0
                || parse_decimal_u64(fields[5], &entry.nlink) != 0
                || parse_decimal_u64(fields[6], &entry.entry_count) != 0
                || parse_decimal_u64(fields[7], &entry.bytes) != 0
                || parse_sha256(fields[8], entry.digest) != 0
                || strcmp(fields[9], TREE_CANONICALIZATION) != 0) {
                return error_code == NULL
                    ? reject("manifest_tree_entry_invalid")
                    : -1;
            }
        } else if (field_count == 14U
                   && strcmp(fields[0], "EXEC_PLAN") == 0) {
            if (assign_execution_plan(result, fields) != 0) {
                return -1;
            }
            line = next_line + 1;
            continue;
        } else {
            return reject("manifest_entry_schema_invalid");
        }
        if (append_manifest_entry(result, &entry) != 0) {
            return -1;
        }
        line = next_line + 1;
    }
    if (result->count == 0U) {
        return reject("manifest_empty");
    }
    return 0;
}

static int read_manifest(
    const char *path,
    const uint8_t expected_digest[CUR0S_SHA256_DIGEST_BYTES],
    char **payload,
    size_t *payload_bytes,
    observation *result
) {
    struct stat initial_information;
    struct stat final_information;
    stat_identity initial_identity;
    stat_identity final_identity;
    cur0s_sha256_context context;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    char *buffer;
    size_t expected_bytes;
    size_t offset = 0U;
    int descriptor = open_absolute_nofollow(path, 0);

    if (descriptor < 0) {
        return -1;
    }
    if (fstat(descriptor, &initial_information) != 0
        || !S_ISREG(initial_information.st_mode)
        || initial_information.st_nlink != 1
        || initial_information.st_size <= 0
        || (uint64_t)initial_information.st_size > MAX_MANIFEST_BYTES) {
        close(descriptor);
        return reject("manifest_stat_invalid");
    }
    initial_identity = identity_from_stat(&initial_information);
    expected_bytes = (size_t)initial_information.st_size;
    buffer = malloc(expected_bytes + 1U);
    if (buffer == NULL) {
        close(descriptor);
        return reject("memory_allocation_failed");
    }
    cur0s_sha256_init(&context);
    while (offset < expected_bytes) {
        ssize_t received = read(descriptor, buffer + offset, expected_bytes - offset);

        if (received < 0 && errno == EINTR) {
            continue;
        }
        if (received <= 0) {
            free(buffer);
            close(descriptor);
            return reject("manifest_read_truncated");
        }
        cur0s_sha256_update(&context, buffer + offset, (size_t)received);
        offset += (size_t)received;
    }
    for (;;) {
        char extra;
        ssize_t received = read(descriptor, &extra, 1U);

        if (received < 0 && errno == EINTR) {
            continue;
        }
        if (received < 0) {
            free(buffer);
            close(descriptor);
            return reject("manifest_read_failed");
        }
        if (received != 0) {
            free(buffer);
            close(descriptor);
            return reject("manifest_grew_during_read");
        }
        break;
    }
    cur0s_sha256_final(&context, digest);
    if (fstat(descriptor, &final_information) != 0) {
        free(buffer);
        close(descriptor);
        return reject("manifest_final_stat_failed");
    }
    final_identity = identity_from_stat(&final_information);
    if (close(descriptor) != 0) {
        free(buffer);
        return reject("manifest_close_failed");
    }
    if (!identities_equal(&initial_identity, &final_identity)) {
        free(buffer);
        return reject("manifest_changed_during_read");
    }
    if (reopen_identity_matches(path, 0, &final_identity) != 0) {
        free(buffer);
        return -1;
    }
    if (memcmp(digest, expected_digest, sizeof(digest)) != 0) {
        free(buffer);
        return reject("manifest_sha256_mismatch");
    }
    buffer[expected_bytes] = '\0';
    result->identity = final_identity;
    memcpy(result->digest, digest, sizeof(result->digest));
    result->bytes = (uint64_t)expected_bytes;
    result->entry_count = 0U;
    *payload = buffer;
    *payload_bytes = expected_bytes;
    return 0;
}

static void free_tree_records(tree_record_list *value) {
    for (size_t index = 0; index < value->count; ++index) {
        free(value->records[index].relative_path);
        free(value->records[index].target);
    }
    free(value->records);
    memset(value, 0, sizeof(*value));
}

static int append_tree_record(
    tree_record_list *value,
    record_type type,
    const char *relative_path,
    mode_t mode,
    uint64_t bytes,
    const uint8_t digest[CUR0S_SHA256_DIGEST_BYTES],
    const char *target
) {
    tree_record *expanded;
    tree_record *record;
    size_t next_capacity;
    int printed;

    if (value->count >= MAX_TREE_ENTRIES) {
        return reject("tree_entry_limit_exceeded");
    }
    if (value->count == value->capacity) {
        next_capacity = value->capacity == 0U ? 128U : value->capacity * 2U;
        expanded = realloc(value->records, next_capacity * sizeof(*expanded));
        if (expanded == NULL) {
            return reject("memory_allocation_failed");
        }
        value->records = expanded;
        value->capacity = next_capacity;
    }
    record = &value->records[value->count];
    memset(record, 0, sizeof(*record));
    record->type = type;
    record->relative_path = duplicate_string(relative_path);
    if (record->relative_path == NULL) {
        return -1;
    }
    printed = snprintf(
        record->mode,
        sizeof(record->mode),
        "%04o",
        (unsigned int)(mode & 07777U)
    );
    if (printed != 4) {
        free(record->relative_path);
        record->relative_path = NULL;
        return reject("tree_mode_format_failed");
    }
    record->bytes = bytes;
    if (digest != NULL) {
        memcpy(record->digest, digest, sizeof(record->digest));
    }
    if (target != NULL) {
        record->target = duplicate_string(target);
        if (record->target == NULL) {
            free(record->relative_path);
            record->relative_path = NULL;
            return -1;
        }
    }
    ++value->count;
    return 0;
}

static char *join_relative_path(const char *prefix, const char *name) {
    size_t prefix_bytes = strlen(prefix);
    size_t name_bytes = strlen(name);
    size_t total_bytes = prefix_bytes + (prefix_bytes == 0U ? 0U : 1U) + name_bytes;
    char *result;

    if (total_bytes == 0U || total_bytes > MAX_RELATIVE_PATH_BYTES) {
        reject("tree_relative_path_invalid");
        return NULL;
    }
    result = malloc(total_bytes + 1U);
    if (result == NULL) {
        reject("memory_allocation_failed");
        return NULL;
    }
    if (prefix_bytes == 0U) {
        memcpy(result, name, name_bytes + 1U);
    } else {
        memcpy(result, prefix, prefix_bytes);
        result[prefix_bytes] = '/';
        memcpy(result + prefix_bytes + 1U, name, name_bytes + 1U);
    }
    return result;
}

static int hash_tree_regular_entry(
    int directory_fd,
    const char *name,
    const struct stat *path_information,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES],
    uint64_t *bytes
) {
    struct stat opened_information;
    struct stat final_information;
    struct stat entry_information;
    stat_identity path_identity = identity_from_stat(path_information);
    stat_identity opened_identity;
    stat_identity final_identity;
    stat_identity entry_identity;
    int descriptor = openat(
        directory_fd,
        name,
        O_RDONLY | O_CLOEXEC | O_NOFOLLOW
    );

    if (descriptor < 0) {
        return reject("tree_regular_open_failed");
    }
    if (fstat(descriptor, &opened_information) != 0) {
        close(descriptor);
        return reject("tree_regular_stat_failed");
    }
    opened_identity = identity_from_stat(&opened_information);
    if (!identities_equal(&path_identity, &opened_identity)
        || !S_ISREG(opened_information.st_mode)
        || opened_information.st_nlink != 1) {
        close(descriptor);
        return reject("tree_regular_entry_replaced_or_unsafe");
    }
    if (hash_open_descriptor(descriptor, digest, bytes) != 0) {
        close(descriptor);
        return -1;
    }
    if (fstat(descriptor, &final_information) != 0) {
        close(descriptor);
        return reject("tree_regular_final_stat_failed");
    }
    final_identity = identity_from_stat(&final_information);
    if (close(descriptor) != 0) {
        return reject("tree_regular_close_failed");
    }
    if (fstatat(directory_fd, name, &entry_information, AT_SYMLINK_NOFOLLOW) != 0) {
        return reject("tree_regular_entry_restat_failed");
    }
    entry_identity = identity_from_stat(&entry_information);
    if (!identities_equal(&opened_identity, &final_identity)
        || !identities_equal(&final_identity, &entry_identity)
        || final_information.st_size < 0
        || *bytes != (uint64_t)final_information.st_size) {
        return reject("tree_regular_changed_during_hash");
    }
    return 0;
}

static char *read_tree_symlink(
    int directory_fd,
    const char *name,
    const struct stat *initial_information
) {
    size_t capacity = initial_information->st_size > 0
        ? (size_t)initial_information->st_size + 1U
        : 256U;
    stat_identity initial_identity = identity_from_stat(initial_information);

    while (capacity <= MAX_SYMLINK_TARGET_BYTES) {
        struct stat final_information;
        stat_identity final_identity;
        char *target = malloc(capacity + 1U);
        ssize_t received;

        if (target == NULL) {
            reject("memory_allocation_failed");
            return NULL;
        }
        received = readlinkat(directory_fd, name, target, capacity);
        if (received < 0) {
            free(target);
            reject("tree_symlink_read_failed");
            return NULL;
        }
        if ((size_t)received == capacity) {
            free(target);
            if (capacity > MAX_SYMLINK_TARGET_BYTES / 2U) {
                break;
            }
            capacity *= 2U;
            continue;
        }
        target[received] = '\0';
        if (!valid_utf8(target)) {
            free(target);
            reject("tree_symlink_target_not_utf8");
            return NULL;
        }
        if (fstatat(directory_fd, name, &final_information, AT_SYMLINK_NOFOLLOW) != 0) {
            free(target);
            reject("tree_symlink_restat_failed");
            return NULL;
        }
        final_identity = identity_from_stat(&final_information);
        if (!identities_equal(&initial_identity, &final_identity)) {
            free(target);
            reject("tree_symlink_changed_during_read");
            return NULL;
        }
        return target;
    }
    reject("tree_symlink_target_oversize");
    return NULL;
}

static char *read_absolute_symlink_once(
    const char *path,
    stat_identity *identity
) {
    int parent_descriptor = -1;
    char *leaf = NULL;
    char *target = NULL;
    size_t capacity;
    struct stat initial_information;
    struct stat final_information;
    stat_identity initial_identity;
    int success = 0;

    if (open_absolute_parent_nofollow(path, &parent_descriptor, &leaf) != 0) {
        return NULL;
    }
    if (fstatat(
            parent_descriptor,
            leaf,
            &initial_information,
            AT_SYMLINK_NOFOLLOW
        ) != 0
        || !S_ISLNK(initial_information.st_mode)
        || initial_information.st_nlink != 1
        || initial_information.st_size < 0
        || (uint64_t)initial_information.st_size > MAX_SYMLINK_TARGET_BYTES) {
        reject("symlink_stat_invalid");
        goto cleanup;
    }
    initial_identity = identity_from_stat(&initial_information);
    capacity = initial_information.st_size > 0
        ? (size_t)initial_information.st_size + 1U
        : 256U;
    while (capacity <= MAX_SYMLINK_TARGET_BYTES) {
        ssize_t received;

        target = malloc(capacity + 1U);
        if (target == NULL) {
            reject("memory_allocation_failed");
            goto cleanup;
        }
        received = readlinkat(parent_descriptor, leaf, target, capacity);
        if (received < 0) {
            reject("symlink_read_failed");
            goto cleanup;
        }
        if ((size_t)received == capacity) {
            free(target);
            target = NULL;
            if (capacity > MAX_SYMLINK_TARGET_BYTES / 2U) {
                reject("symlink_target_oversize");
                goto cleanup;
            }
            capacity *= 2U;
            continue;
        }
        target[received] = '\0';
        if (!canonical_manifest_text(target, MAX_SYMLINK_TARGET_BYTES)) {
            reject("symlink_target_not_canonical_manifest_text");
            goto cleanup;
        }
        break;
    }
    if (target == NULL) {
        reject("symlink_target_oversize");
        goto cleanup;
    }
    if (fstatat(
            parent_descriptor,
            leaf,
            &final_information,
            AT_SYMLINK_NOFOLLOW
        ) != 0) {
        reject("symlink_restat_failed");
        free(target);
        target = NULL;
        goto cleanup;
    }
    {
        stat_identity final_identity = identity_from_stat(&final_information);

        if (!identities_equal(&initial_identity, &final_identity)) {
            reject("symlink_changed_during_read");
            free(target);
            target = NULL;
            goto cleanup;
        }
        *identity = final_identity;
        success = 1;
    }

cleanup:
    free(leaf);
    if (!success) {
        free(target);
        target = NULL;
    }
    if (parent_descriptor >= 0 && close(parent_descriptor) != 0 && success) {
        free(target);
        target = NULL;
        reject("symlink_parent_close_failed");
    }
    return target;
}

static int duplicate_cloexec(int descriptor) {
    int duplicate = dup(descriptor);

    if (duplicate < 0) {
        reject("tree_directory_dup_failed");
        return -1;
    }
    if (fcntl(duplicate, F_SETFD, FD_CLOEXEC) != 0) {
        close(duplicate);
        reject("tree_directory_cloexec_failed");
        return -1;
    }
    return duplicate;
}

static int tree_symlink_target_is_internal(
    const char *relative_path,
    const char *target
) {
    const char *separator;
    const char *cursor;
    size_t depth = 0U;

    if (target == NULL || target[0] == '\0' || target[0] == '/') {
        return 0;
    }
    for (cursor = relative_path; (separator = strchr(cursor, '/')) != NULL;) {
        ++depth;
        cursor = separator + 1;
    }
    cursor = target;
    while (*cursor != '\0') {
        size_t bytes;

        separator = strchr(cursor, '/');
        bytes = separator == NULL ? strlen(cursor) : (size_t)(separator - cursor);
        if (bytes == 0U || (bytes == 1U && cursor[0] == '.')) {
            /* POSIX normalization removes empty and current-directory tokens. */
        } else if (bytes == 2U && cursor[0] == '.' && cursor[1] == '.') {
            if (depth == 0U) {
                return 0;
            }
            --depth;
        } else {
            ++depth;
        }
        if (separator == NULL) {
            break;
        }
        cursor = separator + 1;
    }
    return depth > 0U;
}

static int walk_tree(
    int directory_fd,
    const char *prefix,
    size_t depth,
    tree_record_list *records
) {
    int duplicate;
    DIR *directory;

    if (depth > MAX_TREE_DEPTH) {
        return reject("tree_depth_limit_exceeded");
    }
    duplicate = duplicate_cloexec(directory_fd);
    if (duplicate < 0) {
        return -1;
    }
    directory = fdopendir(duplicate);
    if (directory == NULL) {
        close(duplicate);
        return reject("tree_fdopendir_failed");
    }
    for (;;) {
        struct dirent *item;
        struct stat information;
        stat_identity initial_identity;
        char *relative_path;

        errno = 0;
        item = readdir(directory);
        if (item == NULL) {
            if (errno != 0) {
                closedir(directory);
                return reject("tree_readdir_failed");
            }
            break;
        }
        if (strcmp(item->d_name, ".") == 0 || strcmp(item->d_name, "..") == 0) {
            continue;
        }
        if (!valid_utf8(item->d_name)) {
            closedir(directory);
            return reject("tree_entry_name_not_utf8");
        }
        relative_path = join_relative_path(prefix, item->d_name);
        if (relative_path == NULL) {
            closedir(directory);
            return -1;
        }
        if (fstatat(directory_fd, item->d_name, &information, AT_SYMLINK_NOFOLLOW) != 0) {
            free(relative_path);
            closedir(directory);
            return reject("tree_entry_lstat_failed");
        }
        initial_identity = identity_from_stat(&information);
        if ((strcmp(item->d_name, "__pycache__") == 0
             || (prefix[0] == '\0'
                 && strcmp(item->d_name, "site-packages") == 0))) {
            if (!S_ISDIR(information.st_mode)) {
                free(relative_path);
                closedir(directory);
                return reject("tree_excluded_directory_name_not_directory");
            }
            free(relative_path);
            continue;
        }
        {
            size_t name_bytes = strlen(item->d_name);

            if (name_bytes >= 4U
                && strcmp(item->d_name + name_bytes - 4U, ".pyc") == 0) {
                if (!S_ISREG(information.st_mode)
                    || information.st_nlink != 1) {
                    free(relative_path);
                    closedir(directory);
                    return reject("tree_excluded_pyc_not_regular");
                }
                free(relative_path);
                continue;
            }
        }
        if (S_ISDIR(information.st_mode)) {
            struct stat opened_information;
            struct stat final_information;
            struct stat entry_information;
            stat_identity opened_identity;
            stat_identity final_identity;
            stat_identity entry_identity;
            int child_fd;

            if (append_tree_record(
                    records,
                    RECORD_DIRECTORY,
                    relative_path,
                    information.st_mode,
                    0U,
                    NULL,
                    NULL
                ) != 0) {
                free(relative_path);
                closedir(directory);
                return -1;
            }
            child_fd = openat(
                directory_fd,
                item->d_name,
                O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW
            );
            if (child_fd < 0 || fstat(child_fd, &opened_information) != 0) {
                if (child_fd >= 0) {
                    close(child_fd);
                }
                free(relative_path);
                closedir(directory);
                return reject("tree_directory_open_failed");
            }
            opened_identity = identity_from_stat(&opened_information);
            if (!identities_equal(&initial_identity, &opened_identity)) {
                close(child_fd);
                free(relative_path);
                closedir(directory);
                return reject("tree_directory_entry_replaced");
            }
            if (depth == MAX_TREE_DEPTH
                || walk_tree(child_fd, relative_path, depth + 1U, records) != 0) {
                if (error_code == NULL) {
                    reject("tree_depth_limit_exceeded");
                }
                close(child_fd);
                free(relative_path);
                closedir(directory);
                return -1;
            }
            if (fstat(child_fd, &final_information) != 0) {
                close(child_fd);
                free(relative_path);
                closedir(directory);
                return reject("tree_directory_final_stat_failed");
            }
            final_identity = identity_from_stat(&final_information);
            if (close(child_fd) != 0
                || fstatat(
                    directory_fd,
                    item->d_name,
                    &entry_information,
                    AT_SYMLINK_NOFOLLOW
                ) != 0) {
                free(relative_path);
                closedir(directory);
                return reject("tree_directory_restat_failed");
            }
            entry_identity = identity_from_stat(&entry_information);
            if (!identities_equal(&opened_identity, &final_identity)
                || !identities_equal(&final_identity, &entry_identity)) {
                free(relative_path);
                closedir(directory);
                return reject("tree_directory_changed_during_walk");
            }
        } else if (S_ISLNK(information.st_mode)) {
            char *target = read_tree_symlink(directory_fd, item->d_name, &information);

            if (target != NULL && !tree_symlink_target_is_internal(
                    relative_path, target
                )) {
                reject("tree_external_symlink_forbidden");
            }
            if (target == NULL || error_code != NULL
                || append_tree_record(
                    records,
                    RECORD_SYMLINK,
                    relative_path,
                    information.st_mode,
                    0U,
                    NULL,
                    target
                ) != 0) {
                free(target);
                free(relative_path);
                closedir(directory);
                return -1;
            }
            free(target);
        } else if (S_ISREG(information.st_mode) && information.st_nlink == 1) {
            uint8_t digest[CUR0S_SHA256_DIGEST_BYTES] = {0};
            uint64_t bytes = 0U;

            if (hash_tree_regular_entry(
                    directory_fd,
                    item->d_name,
                    &information,
                    digest,
                    &bytes
                ) != 0
                || append_tree_record(
                    records,
                    RECORD_REGULAR,
                    relative_path,
                    information.st_mode,
                    bytes,
                    digest,
                    NULL
                ) != 0) {
                free(relative_path);
                closedir(directory);
                return -1;
            }
            if (UINT64_MAX - records->regular_bytes < bytes) {
                free(relative_path);
                closedir(directory);
                return reject("tree_regular_bytes_overflow");
            }
            records->regular_bytes += bytes;
        } else {
            free(relative_path);
            closedir(directory);
            return reject("tree_unsafe_entry_type_or_hardlink");
        }
        free(relative_path);
    }
    if (closedir(directory) != 0) {
        return reject("tree_directory_stream_close_failed");
    }
    return 0;
}

static int compare_tree_records(const void *left_value, const void *right_value) {
    const tree_record *left = (const tree_record *)left_value;
    const tree_record *right = (const tree_record *)right_value;

    return strcmp(left->relative_path, right->relative_path);
}

static void hash_text(cur0s_sha256_context *context, const char *value) {
    cur0s_sha256_update(context, value, strlen(value));
}

static void hash_json_string(cur0s_sha256_context *context, const char *value) {
    static const char hex_digits[] = "0123456789abcdef";
    const uint8_t *cursor = (const uint8_t *)value;

    hash_text(context, "\"");
    while (*cursor != 0U) {
        char escaped[6];

        switch (*cursor) {
            case '"':
                hash_text(context, "\\\"");
                break;
            case '\\':
                hash_text(context, "\\\\");
                break;
            case '\b':
                hash_text(context, "\\b");
                break;
            case '\f':
                hash_text(context, "\\f");
                break;
            case '\n':
                hash_text(context, "\\n");
                break;
            case '\r':
                hash_text(context, "\\r");
                break;
            case '\t':
                hash_text(context, "\\t");
                break;
            default:
                if (*cursor < 0x20U) {
                    escaped[0] = '\\';
                    escaped[1] = 'u';
                    escaped[2] = '0';
                    escaped[3] = '0';
                    escaped[4] = hex_digits[*cursor >> 4U];
                    escaped[5] = hex_digits[*cursor & 0x0fU];
                    cur0s_sha256_update(context, escaped, sizeof(escaped));
                } else {
                    cur0s_sha256_update(context, cursor, 1U);
                }
                break;
        }
        ++cursor;
    }
    hash_text(context, "\"");
}

static int canonical_tree_digest(
    tree_record_list *records,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES]
) {
    cur0s_sha256_context context;

    if (records->count > 1U) {
        qsort(
            records->records,
            records->count,
            sizeof(*records->records),
            compare_tree_records
        );
    }
    for (size_t index = 1U; index < records->count; ++index) {
        if (strcmp(
                records->records[index - 1U].relative_path,
                records->records[index].relative_path
            ) == 0) {
            return reject("tree_duplicate_relative_path");
        }
    }
    cur0s_sha256_init(&context);
    hash_text(&context, "[");
    for (size_t index = 0U; index < records->count; ++index) {
        tree_record *record = &records->records[index];

        if (index != 0U) {
            hash_text(&context, ",");
        }
        if (record->type == RECORD_DIRECTORY) {
            hash_text(&context, "{\"mode\":");
            hash_json_string(&context, record->mode);
            hash_text(&context, ",\"relative_path\":");
            hash_json_string(&context, record->relative_path);
            hash_text(&context, ",\"type\":\"directory\"}");
        } else if (record->type == RECORD_SYMLINK) {
            hash_text(&context, "{\"mode\":");
            hash_json_string(&context, record->mode);
            hash_text(&context, ",\"relative_path\":");
            hash_json_string(&context, record->relative_path);
            hash_text(&context, ",\"target\":");
            hash_json_string(&context, record->target);
            hash_text(&context, ",\"type\":\"symlink\"}");
        } else if (record->type == RECORD_REGULAR) {
            char decimal[32];
            char hex[CUR0S_SHA256_HEX_BYTES + 1U];
            int printed = snprintf(
                decimal,
                sizeof(decimal),
                "%" PRIu64,
                record->bytes
            );

            if (printed <= 0 || (size_t)printed >= sizeof(decimal)) {
                return reject("tree_byte_count_format_failed");
            }
            cur0s_sha256_hex(record->digest, hex);
            hash_text(&context, "{\"bytes\":");
            hash_text(&context, decimal);
            hash_text(&context, ",\"mode\":");
            hash_json_string(&context, record->mode);
            hash_text(&context, ",\"relative_path\":");
            hash_json_string(&context, record->relative_path);
            hash_text(&context, ",\"sha256\":");
            hash_json_string(&context, hex);
            hash_text(&context, ",\"type\":\"regular\"}");
        } else {
            return reject("tree_record_type_invalid");
        }
    }
    hash_text(&context, "]");
    cur0s_sha256_final(&context, digest);
    return 0;
}

static int expected_stat_matches(
    const struct stat *information,
    const manifest_entry *expected,
    int directory
) {
    uint64_t observed_size;

    if ((directory && !S_ISDIR(information->st_mode))
        || (!directory && !S_ISREG(information->st_mode))
        || information->st_size < 0) {
        return 0;
    }
    observed_size = (uint64_t)information->st_size;
    return (uint32_t)(information->st_mode & 07777U) == expected->mode
        && (uint64_t)information->st_uid == expected->uid
        && (uint64_t)information->st_gid == expected->gid
        && (uint64_t)information->st_nlink == expected->nlink
        && (directory || information->st_nlink == 1)
        && (directory || observed_size == expected->bytes);
}

static int verify_file_entry(const manifest_entry *expected, observation *result) {
    struct stat initial_information;
    struct stat final_information;
    stat_identity initial_identity;
    stat_identity final_identity;
    uint64_t bytes;
    int descriptor = open_absolute_nofollow(expected->path, 0);

    if (descriptor < 0) {
        return -1;
    }
    if (fstat(descriptor, &initial_information) != 0
        || !expected_stat_matches(&initial_information, expected, 0)) {
        close(descriptor);
        return reject("file_stat_mismatch");
    }
    initial_identity = identity_from_stat(&initial_information);
    if (hash_open_descriptor(descriptor, result->digest, &bytes) != 0) {
        close(descriptor);
        return -1;
    }
    if (fstat(descriptor, &final_information) != 0) {
        close(descriptor);
        return reject("file_final_stat_failed");
    }
    final_identity = identity_from_stat(&final_information);
    if (close(descriptor) != 0) {
        return reject("file_close_failed");
    }
    if (!identities_equal(&initial_identity, &final_identity)) {
        return reject("file_changed_during_hash");
    }
    if (reopen_identity_matches(expected->path, 0, &final_identity) != 0) {
        return -1;
    }
    if (bytes != expected->bytes
        || memcmp(result->digest, expected->digest, sizeof(result->digest)) != 0) {
        return reject("file_sha256_or_size_mismatch");
    }
    result->identity = final_identity;
    result->bytes = bytes;
    result->entry_count = 0U;
    return 0;
}

static int verify_symlink_entry(
    const manifest_entry *expected,
    observation *result
) {
    stat_identity first_identity = {0};
    stat_identity reopened_identity = {0};
    char *first_target = read_absolute_symlink_once(
        expected->path,
        &first_identity
    );
    char *reopened_target = NULL;
    size_t target_bytes;
    cur0s_sha256_context context;

    if (first_target == NULL) {
        return -1;
    }
    if (expected->target == NULL) {
        free(first_target);
        return reject("manifest_symlink_target_missing");
    }
    target_bytes = strlen(first_target);
    if ((uint32_t)(first_identity.mode & 07777U) != expected->mode
        || (uint64_t)first_identity.uid != expected->uid
        || (uint64_t)first_identity.gid != expected->gid
        || (uint64_t)first_identity.nlink != expected->nlink
        || expected->nlink != 1U
        || first_identity.size < 0
        || (uint64_t)first_identity.size != (uint64_t)target_bytes
        || strcmp(first_target, expected->target) != 0) {
        free(first_target);
        return reject("symlink_identity_or_target_mismatch");
    }
    reopened_target = read_absolute_symlink_once(
        expected->path,
        &reopened_identity
    );
    if (reopened_target == NULL) {
        free(first_target);
        return -1;
    }
    if (!identities_equal(&first_identity, &reopened_identity)
        || strcmp(first_target, reopened_target) != 0) {
        free(first_target);
        free(reopened_target);
        return reject("symlink_path_rebound_during_observation");
    }
    cur0s_sha256_init(&context);
    cur0s_sha256_update(&context, first_target, target_bytes);
    cur0s_sha256_final(&context, result->digest);
    result->identity = reopened_identity;
    result->bytes = (uint64_t)target_bytes;
    result->entry_count = 0U;
    free(first_target);
    free(reopened_target);
    return 0;
}

static int verify_tree_entry(const manifest_entry *expected, observation *result) {
    struct stat initial_information;
    struct stat final_information;
    stat_identity initial_identity;
    stat_identity final_identity;
    tree_record_list records = {0};
    int descriptor = open_absolute_nofollow(expected->path, 1);
    int status = -1;

    if (descriptor < 0) {
        return -1;
    }
    if (fstat(descriptor, &initial_information) != 0
        || !expected_stat_matches(&initial_information, expected, 1)) {
        reject("tree_root_stat_mismatch");
        goto cleanup;
    }
    initial_identity = identity_from_stat(&initial_information);
    if (walk_tree(descriptor, "", 0U, &records) != 0
        || canonical_tree_digest(&records, result->digest) != 0) {
        goto cleanup;
    }
    if (fstat(descriptor, &final_information) != 0) {
        reject("tree_root_final_stat_failed");
        goto cleanup;
    }
    final_identity = identity_from_stat(&final_information);
    if (!identities_equal(&initial_identity, &final_identity)) {
        reject("tree_root_changed_during_walk");
        goto cleanup;
    }
    if (reopen_identity_matches(expected->path, 1, &final_identity) != 0) {
        goto cleanup;
    }
    if ((uint64_t)records.count != expected->entry_count
        || records.regular_bytes != expected->bytes
        || memcmp(result->digest, expected->digest, sizeof(result->digest)) != 0) {
        reject("tree_canonical_identity_mismatch");
        goto cleanup;
    }
    result->identity = final_identity;
    result->entry_count = (uint64_t)records.count;
    result->bytes = records.regular_bytes;
    status = 0;

cleanup:
    free_tree_records(&records);
    if (close(descriptor) != 0 && status == 0) {
        return reject("tree_root_close_failed");
    }
    return status;
}

static int verify_entry(const manifest_entry *expected, observation *result) {
    memset(result, 0, sizeof(*result));
    if (expected->type == ENTRY_FILE) {
        return verify_file_entry(expected, result);
    }
    if (expected->type == ENTRY_STDLIB_TREE) {
        return verify_tree_entry(expected, result);
    }
    if (expected->type == ENTRY_SYMLINK) {
        return verify_symlink_entry(expected, result);
    }
    return reject("manifest_entry_type_invalid");
}

static const manifest_entry *find_entry_by_role(
    const manifest *expected,
    const char *role,
    size_t *entry_index
) {
    for (size_t index = 0U; index < expected->count; ++index) {
        if (expected->entries[index].role != NULL
            && strcmp(expected->entries[index].role, role) == 0) {
            *entry_index = index;
            return &expected->entries[index];
        }
    }
    return NULL;
}

static const manifest_entry *find_symlink_by_path(
    const manifest *expected,
    const char *path
) {
    for (size_t index = 0U; index < expected->count; ++index) {
        if (expected->entries[index].type == ENTRY_SYMLINK
            && strcmp(expected->entries[index].path, path) == 0) {
            return &expected->entries[index];
        }
    }
    return NULL;
}

static const manifest_entry *find_file_by_path(
    const manifest *expected,
    const char *path,
    size_t *entry_index
) {
    for (size_t index = 0U; index < expected->count; ++index) {
        if (expected->entries[index].type == ENTRY_FILE
            && strcmp(expected->entries[index].path, path) == 0) {
            *entry_index = index;
            return &expected->entries[index];
        }
    }
    return NULL;
}

static int bind_earliest_native_maps_to_manifest(
    const native_map_snapshot *snapshot,
    const manifest *expected,
    const observation *observations
) {
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    (void)snapshot;
    (void)expected;
    (void)observations;
    return 0;
#else
    if (!snapshot->production_policy_enforced || snapshot->count == 0U) {
        return reject("earliest_native_maps_production_policy_not_enforced");
    }
    for (size_t map_index = 0U; map_index < snapshot->count; ++map_index) {
        const native_map_record *record = &snapshot->records[map_index];
        const char *role = record->runtime_role;
        const manifest_entry *entry;
        const observation *observed;
        uint64_t rounded_remaining;
        size_t entry_index = 0U;

        if (role[0] == '\0') {
            return reject("earliest_native_maps_role_resolution_failed");
        }
        if (strcmp(role, "kernel_vdso") == 0
            || strcmp(role, "kernel_vvar") == 0) {
            if (record->device_major != 0U || record->device_minor != 0U
                || record->inode != 0U || record->offset != 0U) {
                return reject("earliest_native_maps_kernel_identity_invalid");
            }
            continue;
        }
        entry = find_file_by_path(expected, record->path, &entry_index);
        if (entry == NULL) {
            return reject("earliest_native_maps_manifest_file_missing");
        }
        observed = &observations[entry_index];
        if (record->offset >= entry->bytes
            || entry->bytes - record->offset > UINT64_MAX - 4095U) {
            return reject("earliest_native_maps_file_range_invalid");
        }
        rounded_remaining = (
            entry->bytes - record->offset + 4095U
        ) & ~((uint64_t)4095U);
        if ((uint64_t)major(observed->identity.device) != record->device_major
            || (uint64_t)minor(observed->identity.device) != record->device_minor
            || (uint64_t)observed->identity.inode != record->inode
            || record->mapped_bytes > rounded_remaining
            || observed->bytes != entry->bytes
            || memcmp(
                observed->digest,
                entry->digest,
                CUR0S_SHA256_DIGEST_BYTES
                ) != 0) {
            return reject("earliest_native_maps_manifest_identity_mismatch");
        }
        if (strcmp(role, "native-self") == 0
            && (!entry->executable_map_geometry_present
                || record->offset != entry->executable_map_offset
                || record->mapped_bytes
                    != entry->executable_map_mapped_bytes)) {
            return reject("earliest_native_maps_self_geometry_mismatch");
        }
    }
    return 0;
#endif
}

static int symlink_resolves_lexically_to_file(
    const manifest_entry *link,
    const manifest_entry *file
) {
    const char *separator;
    size_t parent_bytes;
    size_t target_bytes;
    size_t expected_bytes;

    if (link == NULL || file == NULL || link->target == NULL) {
        return 0;
    }
    if (link->target[0] == '/') {
        return strcmp(link->target, file->path) == 0;
    }
    if (strchr(link->target, '/') != NULL
        || strcmp(link->target, ".") == 0
        || strcmp(link->target, "..") == 0) {
        return 0;
    }
    separator = strrchr(link->path, '/');
    if (separator == NULL) {
        return 0;
    }
    parent_bytes = (size_t)(separator - link->path);
    target_bytes = strlen(link->target);
    expected_bytes = parent_bytes + 1U + target_bytes;
    return strlen(file->path) == expected_bytes
        && memcmp(file->path, link->path, parent_bytes) == 0
        && file->path[parent_bytes] == '/'
        && memcmp(
            file->path + parent_bytes + 1U,
            link->target,
            target_bytes + 1U
        ) == 0;
}

#if !defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    || CUR0S_NATIVE_PREFLIGHT_TESTING != 1
static int lowercase_sha1_text(const char *value, size_t bytes) {
    if (bytes != 40U) {
        return 0;
    }
    for (size_t index = 0U; index < bytes; ++index) {
        if (!((value[index] >= '0' && value[index] <= '9')
              || (value[index] >= 'a' && value[index] <= 'f'))) {
            return 0;
        }
    }
    return 1;
}
#endif

static int production_launch_paths_and_owners_valid(
    const manifest *expected,
    const arguments_config *config,
    const launch_roles *roles,
    const manifest_entry *python_link
) {
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    (void)expected;
    (void)config;
    (void)roles;
    (void)python_link;
    return 1;
#else
    static const char runner_prefix_suffix[] = "/source/Polymath-AI-";
    static const char runner_tail[] =
        "/scripts/termux/run_cur0s_commercial_sources.py";
    char native_path[MAX_ABSOLUTE_PATH_BYTES + 1U];
    char manifest_path[MAX_ABSOLUTE_PATH_BYTES + 1U];
    char preregistration_path[MAX_ABSOLUTE_PATH_BYTES + 1U];
    char runner_prefix[MAX_ABSOLUTE_PATH_BYTES + 1U];
    size_t runner_prefix_bytes;
    size_t runner_tail_bytes = strlen(runner_tail);
    size_t runner_path_bytes = strlen(roles->runner->path);
    int native_printed;
    int manifest_printed;
    int preregistration_printed;
    int runner_prefix_printed;

    native_printed = snprintf(
        native_path,
        sizeof(native_path),
        "%s/cur0s_native_preflight",
        expected->plan.action_path
    );
    manifest_printed = snprintf(
        manifest_path,
        sizeof(manifest_path),
        "%s/native_preflight.manifest",
        expected->plan.action_path
    );
    preregistration_printed = snprintf(
        preregistration_path,
        sizeof(preregistration_path),
        "%s/preregistration.json",
        expected->plan.action_path
    );
    runner_prefix_printed = snprintf(
        runner_prefix,
        sizeof(runner_prefix),
        "%s%s",
        expected->plan.action_path,
        runner_prefix_suffix
    );
    if (native_printed <= 0 || (size_t)native_printed >= sizeof(native_path)
        || manifest_printed <= 0
        || (size_t)manifest_printed >= sizeof(manifest_path)
        || preregistration_printed <= 0
        || (size_t)preregistration_printed >= sizeof(preregistration_path)
        || runner_prefix_printed <= 0
        || (size_t)runner_prefix_printed >= sizeof(runner_prefix)) {
        return 0;
    }
    runner_prefix_bytes = (size_t)runner_prefix_printed;
    if (runner_path_bytes != runner_prefix_bytes + 40U + runner_tail_bytes
        || memcmp(roles->runner->path, runner_prefix, runner_prefix_bytes) != 0
        || !lowercase_sha1_text(
            roles->runner->path + runner_prefix_bytes,
            40U
        )
        || memcmp(
            roles->runner->path + runner_prefix_bytes + 40U,
            runner_tail,
            runner_tail_bytes + 1U
        ) != 0) {
        return 0;
    }
    return geteuid() == 10536
        && getegid() == 10536
        && strcmp(config->manifest_path, manifest_path) == 0
        && strcmp(roles->native_self->path, native_path) == 0
        && strcmp(roles->preregistration->path, preregistration_path) == 0
        && strcmp(expected->plan.python_argv0, EXPECTED_PYTHON_ARGV0) == 0
        && strcmp(roles->python->path,
                  "/data/data/com.termux/files/usr/bin/python3.13") == 0
        && strcmp(python_link->target, "python3.13") == 0
        && roles->native_self->mode == 0700U
        && roles->native_self->uid == 10536U
        && roles->native_self->gid == 10536U
        && roles->native_self->nlink == 1U
        && roles->native_self->executable_map_geometry_present
        && roles->python->mode == 0700U
        && roles->python->uid == 10536U
        && roles->python->gid == 10536U
        && roles->python->nlink == 1U;
#endif
}

static int collect_launch_roles(
    const manifest *expected,
    const arguments_config *config,
    launch_roles *roles
) {
    const manifest_entry *python_link;

    memset(roles, 0, sizeof(*roles));
    if (!expected->plan.present) {
        return reject("launch_execution_plan_missing");
    }
    if (!config->outer_environment_observed
        || memcmp(
            config->observed_outer_environment_digest,
            expected->plan.outer_environment_digest,
            CUR0S_SHA256_DIGEST_BYTES
        ) != 0) {
        return reject("launch_outer_environment_binding_mismatch");
    }
    roles->native_self = find_entry_by_role(
        expected,
        "native-self",
        &roles->native_self_index
    );
    roles->python = find_entry_by_role(
        expected,
        "python",
        &roles->python_index
    );
    roles->runner = find_entry_by_role(
        expected,
        "runner",
        &roles->runner_index
    );
    roles->preregistration = find_entry_by_role(
        expected,
        "preregistration",
        &roles->preregistration_index
    );
    if (roles->native_self == NULL || roles->python == NULL
        || roles->runner == NULL || roles->preregistration == NULL) {
        return reject("launch_required_file_role_missing");
    }
    if (!config->expected_preregistration_digest_present
        || memcmp(
            config->expected_preregistration_digest,
            roles->preregistration->digest,
            CUR0S_SHA256_DIGEST_BYTES
        ) != 0) {
        return reject("launch_expected_preregistration_sha256_mismatch");
    }
    python_link = find_symlink_by_path(
        expected,
        expected->plan.python_argv0
    );
    if (!symlink_resolves_lexically_to_file(python_link, roles->python)) {
        return reject("launch_python_argv0_symlink_not_bound_to_python_role");
    }
    if ((roles->native_self->mode & 0111U) == 0U
        || (roles->python->mode & 0111U) == 0U) {
        return reject("launch_executable_role_mode_invalid");
    }
    if (roles->runner->mode != 0600U
        || roles->preregistration->mode != 0600U
        || roles->runner->uid != (uint64_t)geteuid()
        || roles->runner->gid != (uint64_t)getegid()
        || roles->preregistration->uid != (uint64_t)geteuid()
        || roles->preregistration->gid != (uint64_t)getegid()
        || roles->runner->nlink != 1U
        || roles->preregistration->nlink != 1U) {
        return reject("launch_private_runner_or_preregistration_identity_invalid");
    }
    if (!production_launch_paths_and_owners_valid(
            expected,
            config,
            roles,
            python_link
        )) {
        return reject("launch_production_paths_or_owners_invalid");
    }
#if !defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    || CUR0S_NATIVE_PREFLIGHT_TESTING != 1
    if (require_path_absent(expected->plan.pycache_prefix) != 0) {
        return -1;
    }
#endif
    return 0;
}

static int open_held_verified_file(
    const manifest_entry *expected,
    const observation *baseline
) {
    struct stat initial_information;
    struct stat final_information;
    stat_identity initial_identity;
    stat_identity final_identity;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    uint64_t bytes = 0U;
    int descriptor = open_absolute_nofollow(expected->path, 0);

    if (descriptor < 0) {
        return -1;
    }
    if (fstat(descriptor, &initial_information) != 0
        || !expected_stat_matches(&initial_information, expected, 0)) {
        close(descriptor);
        return reject("launch_held_file_stat_mismatch");
    }
    initial_identity = identity_from_stat(&initial_information);
    if (!identities_equal(&initial_identity, &baseline->identity)
        || hash_open_descriptor(descriptor, digest, &bytes) != 0) {
        close(descriptor);
        return error_code == NULL
            ? reject("launch_held_file_identity_mismatch")
            : -1;
    }
    if (fstat(descriptor, &final_information) != 0) {
        close(descriptor);
        return reject("launch_held_file_final_stat_failed");
    }
    final_identity = identity_from_stat(&final_information);
    if (!identities_equal(&initial_identity, &final_identity)
        || !identities_equal(&final_identity, &baseline->identity)
        || bytes != expected->bytes
        || memcmp(digest, expected->digest, sizeof(digest)) != 0
        || lseek(descriptor, 0, SEEK_SET) != 0) {
        close(descriptor);
        return reject("launch_held_file_changed_or_digest_mismatch");
    }
    if (reopen_identity_matches(expected->path, 0, &final_identity) != 0) {
        close(descriptor);
        return -1;
    }
    return descriptor;
}

static int open_held_verified_manifest(
    const char *path,
    const uint8_t expected_digest[CUR0S_SHA256_DIGEST_BYTES],
    const observation *baseline
) {
    struct stat information;
    struct stat final_information;
    stat_identity identity;
    stat_identity final_identity;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    uint64_t bytes = 0U;
    int descriptor = open_absolute_nofollow(path, 0);

    if (descriptor < 0) {
        return -1;
    }
    if (fstat(descriptor, &information) != 0
        || !S_ISREG(information.st_mode)
        || (information.st_mode & 07777U) != 0600U
        || information.st_uid != geteuid()
        || information.st_gid != getegid()
        || information.st_nlink != 1) {
        close(descriptor);
        return reject("launch_held_manifest_stat_invalid");
    }
    identity = identity_from_stat(&information);
    if (!identities_equal(&identity, &baseline->identity)
        || hash_open_descriptor(descriptor, digest, &bytes) != 0) {
        close(descriptor);
        return error_code == NULL
            ? reject("launch_held_manifest_identity_mismatch")
            : -1;
    }
    if (fstat(descriptor, &final_information) != 0) {
        close(descriptor);
        return reject("launch_held_manifest_final_stat_failed");
    }
    final_identity = identity_from_stat(&final_information);
    if (!identities_equal(&identity, &final_identity)
        || bytes != baseline->bytes
        || memcmp(digest, expected_digest, sizeof(digest)) != 0
        || lseek(descriptor, 0, SEEK_SET) != 0
        || reopen_identity_matches(path, 0, &final_identity) != 0) {
        close(descriptor);
        return error_code == NULL
            ? reject("launch_held_manifest_changed_or_digest_mismatch")
            : -1;
    }
    return descriptor;
}

static void close_held_launch_descriptors(held_launch_descriptors *held) {
    int *descriptors[] = {
        &held->python_descriptor,
        &held->runner_descriptor,
        &held->manifest_descriptor,
        &held->preregistration_descriptor,
    };

    for (size_t index = 0U; index < sizeof(descriptors) / sizeof(descriptors[0]);
         ++index) {
        if (*descriptors[index] >= 0) {
            close(*descriptors[index]);
            *descriptors[index] = -1;
        }
    }
}

static int verify_running_native_self(
    const manifest_entry *native_self,
    const observation *baseline,
    int native_self_descriptor,
    const char *invocation_path
) {
    struct stat information;
    stat_identity identity;
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
    uint64_t bytes = 0U;
    int descriptor = -1;

#if defined(__ANDROID__)
    (void)native_self_descriptor;
    (void)invocation_path;
    descriptor = open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
#elif defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    if (invocation_path == NULL || strcmp(invocation_path, native_self->path) != 0) {
        return reject("test_launch_native_self_invocation_path_mismatch");
    }
    descriptor = fcntl(native_self_descriptor, F_DUPFD_CLOEXEC, 0);
#else
    (void)native_self;
    (void)baseline;
    (void)native_self_descriptor;
    (void)invocation_path;
    return reject("launch_requires_android_api30");
#endif
    if (descriptor < 0) {
        return reject("launch_proc_self_exe_open_failed");
    }
    if (fstat(descriptor, &information) != 0) {
        close(descriptor);
        return reject("launch_proc_self_exe_stat_failed");
    }
    identity = identity_from_stat(&information);
    if (!identities_equal(&identity, &baseline->identity)
        || hash_open_descriptor(descriptor, digest, &bytes) != 0) {
        close(descriptor);
        return error_code == NULL
            ? reject("launch_native_self_identity_mismatch")
            : -1;
    }
    if (close(descriptor) != 0) {
        return reject("launch_proc_self_exe_close_failed");
    }
    if (bytes != native_self->bytes
        || memcmp(digest, native_self->digest, sizeof(digest)) != 0) {
        return reject("launch_native_self_digest_mismatch");
    }
    return 0;
}

static int prepare_held_launch_descriptors(
    const manifest *expected,
    const launch_roles *roles,
    const observation *entry_observations,
    const arguments_config *config,
    const observation *manifest_observation,
    const char *invocation_path,
    held_launch_descriptors *held
) {
    int native_self_descriptor = -1;

    held->python_descriptor = -1;
    held->runner_descriptor = -1;
    held->manifest_descriptor = -1;
    held->preregistration_descriptor = -1;
    native_self_descriptor = open_held_verified_file(
        roles->native_self,
        &entry_observations[roles->native_self_index]
    );
    if (native_self_descriptor < 0
        || verify_running_native_self(
            roles->native_self,
            &entry_observations[roles->native_self_index],
            native_self_descriptor,
            invocation_path
        ) != 0) {
        if (native_self_descriptor >= 0) {
            close(native_self_descriptor);
        }
        return -1;
    }
    if (close(native_self_descriptor) != 0) {
        return reject("launch_native_self_descriptor_close_failed");
    }
    held->python_descriptor = open_held_verified_file(
        roles->python,
        &entry_observations[roles->python_index]
    );
    held->runner_descriptor = open_held_verified_file(
        roles->runner,
        &entry_observations[roles->runner_index]
    );
    held->preregistration_descriptor = open_held_verified_file(
        roles->preregistration,
        &entry_observations[roles->preregistration_index]
    );
    held->manifest_descriptor = open_held_verified_manifest(
        config->manifest_path,
        config->manifest_digest,
        manifest_observation
    );
    if (held->python_descriptor < 0 || held->runner_descriptor < 0
        || held->preregistration_descriptor < 0
        || held->manifest_descriptor < 0) {
        close_held_launch_descriptors(held);
        return error_code == NULL
            ? reject("launch_required_descriptor_open_failed")
            : -1;
    }
    (void)expected;
    return 0;
}

static int append_digest_string(
    text_buffer *output,
    const uint8_t digest[CUR0S_SHA256_DIGEST_BYTES]
) {
    char hex[CUR0S_SHA256_HEX_BYTES + 1U];
    char tagged[7U + CUR0S_SHA256_HEX_BYTES + 1U];
    int printed;

    cur0s_sha256_hex(digest, hex);
    printed = snprintf(tagged, sizeof(tagged), "sha256:%s", hex);
    if (printed <= 0 || (size_t)printed >= sizeof(tagged)) {
        return reject("native_attestation_digest_format_failed");
    }
    return append_json_string_value(output, tagged);
}

static int append_attested_role(
    text_buffer *output,
    const manifest_entry *entry
) {
    if (append_text(output, "{\"bytes\":") != 0
        || append_u64(output, entry->bytes) != 0
        || append_text(output, ",\"path\":") != 0
        || append_json_string_value(output, entry->path) != 0
        || append_text(output, ",\"sha256\":") != 0
        || append_digest_string(output, entry->digest) != 0
        || append_text(output, "}") != 0) {
        return -1;
    }
    return 0;
}

static int append_native_map_record_identity(
    text_buffer *output,
    const native_map_record *record,
    const manifest *expected
) {
    const manifest_entry *entry = NULL;
    size_t entry_index = 0U;
    int kernel_record = strcmp(record->runtime_role, "kernel_vdso") == 0
        || strcmp(record->runtime_role, "kernel_vvar") == 0;

    if (!kernel_record) {
        entry = find_file_by_path(expected, record->path, &entry_index);
        if (entry == NULL) {
            return reject("native_maps_attestation_manifest_file_missing");
        }
    }
    if (append_text(output, "{\"bytes\":") != 0
        || (kernel_record
            ? append_text(output, "null")
            : append_u64(output, entry->bytes)) != 0
        || append_text(output, ",\"device_major\":") != 0
        || append_u64(output, record->device_major) != 0
        || append_text(output, ",\"device_minor\":") != 0
        || append_u64(output, record->device_minor) != 0
        || append_text(output, ",\"inode\":") != 0
        || append_u64(output, record->inode) != 0
        || append_text(output, ",\"mapped_bytes\":") != 0
        || append_u64(output, record->mapped_bytes) != 0
        || append_text(output, ",\"offset\":") != 0
        || append_u64(output, record->offset) != 0
        || append_text(output, ",\"path\":") != 0
        || append_json_string_value(output, record->path) != 0
        || append_text(output, ",\"permissions\":") != 0
        || append_json_string_value(output, record->permissions) != 0
        || append_text(output, ",\"runtime_role\":") != 0
        || append_json_string_value(output, record->runtime_role) != 0
        || append_text(output, ",\"sha256\":") != 0
        || (kernel_record
            ? append_text(output, "null")
            : append_digest_string(output, entry->digest)) != 0
        || append_text(output, "}") != 0) {
        return -1;
    }
    return 0;
}

static int build_native_maps_identity(
    const native_map_snapshot *snapshot,
    const manifest *expected,
    text_buffer *output
) {
    if (append_text(
            output,
            "{\"capture_timing\":\"first_action_in_main_before_argument_parsing\"," 
            "\"executable_mapping_policy\":\"exact_nine_record_phone_native_"
            "runtime_closure_only\",\"production_policy_enforced\":"
        ) != 0
        || append_text(
            output,
            snapshot->production_policy_enforced ? "true" : "false"
        ) != 0
        || append_text(output, ",\"records\":[") != 0) {
        return -1;
    }
    for (size_t index = 0U; index < snapshot->count; ++index) {
        if ((index != 0U && append_text(output, ",") != 0)
            || append_native_map_record_identity(
                output,
                &snapshot->records[index],
                expected
            ) != 0) {
            return -1;
        }
    }
    if (append_text(
            output,
            "],\"schema_version\":\"cur0s_native_earliest_main_maps_v1\"," 
            "\"unexpected_executable_mappings_absent\":"
        ) != 0
        || append_text(
            output,
            snapshot->production_policy_enforced ? "true" : "false"
        ) != 0
        || append_text(output, ",\"vvar\":{\"nonexecutable\":") != 0
        || append_text(
            output,
            snapshot->vvar_present ? "true" : "null"
        ) != 0
        || append_text(output, ",\"present\":") != 0
        || append_text(output, snapshot->vvar_present ? "true" : "false") != 0
        || append_text(output, "}}") != 0) {
        return -1;
    }
    return 0;
}

static int build_native_attestation(
    const manifest *expected,
    const launch_roles *roles,
    const arguments_config *config,
    const text_buffer *native_maps,
    text_buffer *output
) {
    uint8_t native_maps_digest[CUR0S_SHA256_DIGEST_BYTES];
    cur0s_sha256_context native_maps_context;

    cur0s_sha256_init(&native_maps_context);
    cur0s_sha256_update(
        &native_maps_context,
        native_maps->data,
        native_maps->length
    );
    cur0s_sha256_final(&native_maps_context, native_maps_digest);
    if (append_text(output, "{\"entries_verified\":") != 0
        || append_u64(output, (uint64_t)expected->count) != 0
        || append_text(
            output,
            ",\"fixed_fds\":{\"manifest\":5,"
            "\"native_attestation\":4,\"preregistration\":6,"
            "\"python_exec_cloexec\":7,\"runner\":3}"
        ) != 0
        || append_text(
            output,
            ",\"helper_dependency_swap_safety_claimed\":false,"
            "\"manifest_sha256\":"
        ) != 0
        || append_digest_string(output, config->manifest_digest) != 0
        || append_text(
            output,
            ",\"mode\":\"launch\",\"native_maps\":"
        ) != 0
        || append_text_bytes(output, native_maps->data, native_maps->length) != 0
        || append_text(output, ",\"native_maps_root_sha256\":") != 0
        || append_digest_string(output, native_maps_digest) != 0
        || append_text(
            output,
            ",\"outer_env_observed\":true,"
            "\"outer_environment_sha256\":"
        ) != 0
        || append_digest_string(
            output,
            config->observed_outer_environment_digest
        ) != 0
        || append_text(
            output,
            ",\"passes_completed\":2,"
            "\"persistent_writes\":false,\"pid\":"
        ) != 0
        || append_u64(output, (uint64_t)getpid()) != 0
        || append_text(output, ",\"python_pycache_prefix\":") != 0
        || append_json_string_value(output, expected->plan.pycache_prefix) != 0
        || append_text(output, ",\"python_pycache_prefix_absent\":true") != 0
        || append_text(output, ",\"roles\":{\"native-self\":") != 0
        || append_attested_role(output, roles->native_self) != 0
        || append_text(output, ",\"preregistration\":") != 0
        || append_attested_role(output, roles->preregistration) != 0
        || append_text(output, ",\"python\":") != 0
        || append_attested_role(output, roles->python) != 0
        || append_text(output, ",\"runner\":") != 0
        || append_attested_role(output, roles->runner) != 0
        || append_text(output, "},\"run_id\":") != 0
        || append_json_string_value(output, expected->plan.run_id) != 0
        || append_text(
            output,
            ",\"schema_version\":\"cur0s_native_launch_attestation_v2\","
            "\"security_ceiling\":"
        ) != 0
        || append_json_string_value(output, SECURITY_CEILING) != 0
        || append_text(output, ",\"status\":\"verified\"}") != 0) {
        return -1;
    }
    return 0;
}

#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
static int append_launch_argv(
    text_buffer *output,
    const manifest *expected,
    const launch_roles *roles,
    const arguments_config *config
) {
    const char *literal_values[11];
    char preregistration_hex[CUR0S_SHA256_HEX_BYTES + 1U];
    char preregistration_tagged[7U + CUR0S_SHA256_HEX_BYTES + 1U];
    char pycache_argument[MAX_ABSOLUTE_PATH_BYTES + 17U];
    int printed;

    cur0s_sha256_hex(config->expected_preregistration_digest, preregistration_hex);
    printed = snprintf(
        preregistration_tagged,
        sizeof(preregistration_tagged),
        "sha256:%s",
        preregistration_hex
    );
    if (printed <= 0 || (size_t)printed >= sizeof(preregistration_tagged)) {
        return reject("launch_preregistration_digest_format_failed");
    }
    printed = snprintf(
        pycache_argument,
        sizeof(pycache_argument),
        "pycache_prefix=%s",
        expected->plan.pycache_prefix
    );
    if (printed <= 0 || (size_t)printed >= sizeof(pycache_argument)) {
        return reject("launch_pycache_argument_format_failed");
    }
    literal_values[0] = expected->plan.python_argv0;
    literal_values[1] = PYTHON_COMBINED_FLAGS;
    literal_values[2] = PYTHON_XOPTION_FLAG;
    literal_values[3] = pycache_argument;
    literal_values[4] = "/proc/self/fd/3";
    literal_values[5] = "--preregistration";
    literal_values[6] = roles->preregistration->path;
    literal_values[7] = "--expected-preregistration-sha256";
    literal_values[8] = preregistration_tagged;
    literal_values[9] = "--output-dir";
    literal_values[10] = expected->plan.output_path;
    if (append_text(output, "[") != 0) {
        return -1;
    }
    for (size_t index = 0U;
         index < sizeof(literal_values) / sizeof(literal_values[0]);
         ++index) {
        if ((index != 0U && append_text(output, ",") != 0)
            || append_json_string_value(output, literal_values[index]) != 0) {
            return -1;
        }
    }
    return append_text(output, "]");
}

static int emit_test_launch_plan(
    const manifest *expected,
    const launch_roles *roles,
    const arguments_config *config,
    const text_buffer *attestation
) {
    text_buffer output = {0};
    uint8_t attestation_digest[CUR0S_SHA256_DIGEST_BYTES];
    cur0s_sha256_context context;
    int status = -1;

    cur0s_sha256_init(&context);
    cur0s_sha256_update(&context, attestation->data, attestation->length);
    cur0s_sha256_final(&context, attestation_digest);
    if (append_text(&output, "{\"argv\":") != 0
        || append_launch_argv(&output, expected, roles, config) != 0
        || append_text(&output, ",\"environment\":") != 0
        || append_text(&output, LAUNCH_ENVIRONMENT_JSON) != 0
        || append_text(
            &output,
            ",\"fixed_fds\":{\"manifest\":5,"
            "\"native_attestation\":4,\"preregistration\":6,"
            "\"python_exec_cloexec\":7,\"runner\":3},"
            "\"memfd_required_seals\":[\"F_SEAL_GROW\",\"F_SEAL_SEAL\","
            "\"F_SEAL_SHRINK\",\"F_SEAL_WRITE\"],"
            "\"mode\":\"test_launch_plan\",\"native_attestation\":"
        ) != 0
        || append_text_bytes(&output, attestation->data, attestation->length) != 0
        || append_text(&output, ",\"native_attestation_sha256\":") != 0
        || append_digest_string(&output, attestation_digest) != 0
        || append_text(
            &output,
            ",\"production_launch_performed\":false,"
            "\"schema_version\":\"cur0s_native_launch_plan_v1\","
            "\"status\":\"verified\"}"
        ) != 0) {
        goto cleanup;
    }
    if (fwrite(output.data, 1U, output.length, stdout) != output.length
        || fputc('\n', stdout) == EOF) {
        reject("test_launch_plan_emit_failed");
        goto cleanup;
    }
    status = 0;

cleanup:
    free_text_buffer(&output);
    return status;
}
#endif

#if defined(CUR0S_COMPILE_ANDROID_LAUNCH)
static int relocate_owned_descriptor(int *descriptor) {
    int relocated = fcntl(
        *descriptor,
        F_DUPFD_CLOEXEC,
        RELOCATED_DESCRIPTOR_MINIMUM
    );

    if (relocated < 0) {
        return reject("launch_descriptor_relocation_failed");
    }
    if (close(*descriptor) != 0) {
        close(relocated);
        return reject("launch_original_descriptor_close_failed");
    }
    *descriptor = -1;
    return relocated;
}

static int write_all_descriptor(int descriptor, const char *payload, size_t bytes) {
    size_t offset = 0U;

    while (offset < bytes) {
        ssize_t written = write(descriptor, payload + offset, bytes - offset);

        if (written < 0 && errno == EINTR) {
            continue;
        }
        if (written <= 0) {
            return reject("native_attestation_memfd_write_failed");
        }
        offset += (size_t)written;
    }
    return 0;
}

static int create_sealed_attestation_memfd(const text_buffer *attestation) {
    const int required_seals = F_SEAL_WRITE
        | F_SEAL_GROW
        | F_SEAL_SHRINK
        | F_SEAL_SEAL;
    struct stat information;
    int descriptor = memfd_create(
        "cur0s-native-attestation",
        MFD_CLOEXEC | MFD_ALLOW_SEALING
    );

    if (descriptor < 0) {
        return reject("native_attestation_memfd_create_failed");
    }
    if (fchmod(descriptor, 0400) != 0
        || write_all_descriptor(
            descriptor,
            attestation->data,
            attestation->length
        ) != 0
        || fcntl(descriptor, F_ADD_SEALS, required_seals) != 0
        || fcntl(descriptor, F_GET_SEALS) != required_seals
        || fstat(descriptor, &information) != 0
        || !S_ISREG(information.st_mode)
        || (information.st_mode & 07777U) != 0400U
        || information.st_nlink != 0
        || information.st_size < 0
        || (uint64_t)information.st_size != (uint64_t)attestation->length
        || lseek(descriptor, 0, SEEK_SET) != 0) {
        close(descriptor);
        return error_code == NULL
            ? reject("native_attestation_memfd_seal_or_identity_invalid")
            : -1;
    }
    return descriptor;
}

static int bind_descriptor(int source, int target, int close_on_exec) {
    int descriptor_flags = close_on_exec ? FD_CLOEXEC : 0;

    if (source != target && dup2(source, target) != target) {
        return reject("launch_fixed_descriptor_binding_failed");
    }
    if (fcntl(target, F_SETFD, descriptor_flags) != 0) {
        return reject("launch_fixed_descriptor_flag_failed");
    }
    return 0;
}

static int verify_fixed_attestation_descriptor(size_t expected_bytes) {
    const int required_seals = F_SEAL_WRITE
        | F_SEAL_GROW
        | F_SEAL_SHRINK
        | F_SEAL_SEAL;
    struct stat information;

    if (fstat(ATTESTATION_DESCRIPTOR, &information) != 0
        || !S_ISREG(information.st_mode)
        || (information.st_mode & 07777U) != 0400U
        || information.st_nlink != 0
        || information.st_size < 0
        || (uint64_t)information.st_size != (uint64_t)expected_bytes
        || fcntl(ATTESTATION_DESCRIPTOR, F_GET_SEALS) != required_seals
        || fcntl(ATTESTATION_DESCRIPTOR, F_GETFD) != 0
        || lseek(ATTESTATION_DESCRIPTOR, 0, SEEK_CUR) != 0) {
        return reject("launch_fixed_attestation_descriptor_invalid");
    }
    return 0;
}

static int verify_fixed_private_descriptor(int descriptor) {
    struct stat information;

    if (fstat(descriptor, &information) != 0
        || !S_ISREG(information.st_mode)
        || (information.st_mode & 07777U) != 0600U
        || information.st_uid != geteuid()
        || information.st_gid != getegid()
        || information.st_nlink != 1
        || fcntl(descriptor, F_GETFD) != 0
        || lseek(descriptor, 0, SEEK_CUR) != 0) {
        return reject("launch_fixed_private_descriptor_invalid");
    }
    return 0;
}

static int close_relocated_descriptor(int *descriptor) {
    if (*descriptor < 0) {
        return 0;
    }
    if (close(*descriptor) != 0) {
        *descriptor = -1;
        return reject("launch_relocated_descriptor_close_failed");
    }
    *descriptor = -1;
    return 0;
}

static int parse_open_descriptor_name(const char *name, int *descriptor) {
    uint64_t parsed = 0U;

    if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
        return 0;
    }
    if (name[0] == '\0' || (name[0] == '0' && name[1] != '\0')) {
        return reject("launch_ambient_descriptor_entry_invalid");
    }
    for (const char *cursor = name; *cursor != '\0'; ++cursor) {
        unsigned int digit;

        if (*cursor < '0' || *cursor > '9') {
            return reject("launch_ambient_descriptor_entry_invalid");
        }
        digit = (unsigned int)(*cursor - '0');
        if (parsed > (uint64_t)(INT_MAX - (int)digit) / 10U) {
            return reject("launch_ambient_descriptor_entry_invalid");
        }
        parsed = (parsed * 10U) + (uint64_t)digit;
    }
    *descriptor = (int)parsed;
    return 1;
}

static int mark_descriptor_close_on_exec(int descriptor) {
    int flags = fcntl(descriptor, F_GETFD);
    int verified_flags;

    if (flags < 0 || fcntl(descriptor, F_SETFD, flags | FD_CLOEXEC) != 0) {
        return reject("launch_ambient_descriptor_cloexec_failed");
    }
    verified_flags = fcntl(descriptor, F_GETFD);
    if (verified_flags < 0 || (verified_flags & FD_CLOEXEC) == 0) {
        return reject("launch_ambient_descriptor_cloexec_failed");
    }
    return 0;
}

/*
 * At this boundary every owned launch descriptor has already been bound to
 * 3..7 and its relocated duplicate closed.  Enumerating the kernel's own
 * descriptor view is therefore exhaustive and cannot retire an owned handle.
 * Every descriptor >= 8, including the transient directory descriptor, is
 * marked close-on-exec.  Any unreadable entry or failed flag transition aborts
 * before execveat.
 */
static int mark_all_ambient_descriptors_close_on_exec(void) {
    DIR *directory = opendir(CUR0S_AMBIENT_DESCRIPTOR_DIRECTORY);
    int status = -1;

    if (directory == NULL) {
        return reject("launch_ambient_descriptor_directory_open_failed");
    }
    for (;;) {
        struct dirent *entry;
        int descriptor;
        int parsed;

        errno = 0;
        entry = readdir(directory);
        if (entry == NULL) {
            if (errno != 0) {
                reject("launch_ambient_descriptor_enumeration_failed");
                break;
            }
            status = 0;
            break;
        }
        parsed = parse_open_descriptor_name(entry->d_name, &descriptor);
        if (parsed < 0) {
            break;
        }
        if (parsed == 0 || descriptor < AMBIENT_DESCRIPTOR_MINIMUM) {
            continue;
        }
        if (mark_descriptor_close_on_exec(descriptor) != 0) {
            break;
        }
    }
    if (closedir(directory) != 0 && status == 0) {
        return reject("launch_ambient_descriptor_directory_close_failed");
    }
    return status;
}

static int execute_android_launch(
    const manifest *expected,
    const launch_roles *roles,
    const arguments_config *config,
    held_launch_descriptors *held,
    const text_buffer *attestation
) {
    enum { PYTHON_EXEC_DESCRIPTOR = 7 };
    char preregistration_hex[CUR0S_SHA256_HEX_BYTES + 1U];
    char preregistration_tagged[7U + CUR0S_SHA256_HEX_BYTES + 1U];
    char pycache_argument[MAX_ABSOLUTE_PATH_BYTES + 17U];
    char *child_arguments[12];
    char *child_environment[] = {
        "ANDROID_ROOT=/system",
        "CUR0S_NATIVE_ATTESTATION_FD=4",
        "CUR0S_NATIVE_MANIFEST_FD=5",
        "CUR0S_PREREGISTRATION_FD=6",
        "HOME=/data/data/com.termux/files/home",
        "LC_ALL=C",
        "LD_PRELOAD=/data/data/com.termux/files/usr/lib/libtermux-exec.so",
        "PATH=/data/data/com.termux/files/usr/bin:/system/bin",
        "TERMUX_EXEC__PROC_SELF_EXE=/data/data/com.termux/files/usr/bin/python",
        NULL,
    };
    int relocated_python = -1;
    int relocated_runner = -1;
    int relocated_manifest = -1;
    int relocated_preregistration = -1;
    int relocated_attestation = -1;
    int attestation_descriptor = -1;
    int printed;

    cur0s_sha256_hex(config->expected_preregistration_digest, preregistration_hex);
    printed = snprintf(
        preregistration_tagged,
        sizeof(preregistration_tagged),
        "sha256:%s",
        preregistration_hex
    );
    if (printed <= 0 || (size_t)printed >= sizeof(preregistration_tagged)) {
        return reject("launch_preregistration_digest_format_failed");
    }
    printed = snprintf(
        pycache_argument,
        sizeof(pycache_argument),
        "pycache_prefix=%s",
        expected->plan.pycache_prefix
    );
    if (printed <= 0 || (size_t)printed >= sizeof(pycache_argument)) {
        return reject("launch_pycache_argument_format_failed");
    }
    relocated_python = relocate_owned_descriptor(&held->python_descriptor);
    relocated_runner = relocate_owned_descriptor(&held->runner_descriptor);
    relocated_manifest = relocate_owned_descriptor(&held->manifest_descriptor);
    relocated_preregistration = relocate_owned_descriptor(
        &held->preregistration_descriptor
    );
    if (relocated_python < 0 || relocated_runner < 0
        || relocated_manifest < 0 || relocated_preregistration < 0) {
        goto cleanup;
    }
    attestation_descriptor = create_sealed_attestation_memfd(attestation);
    if (attestation_descriptor < 0) {
        goto cleanup;
    }
    relocated_attestation = relocate_owned_descriptor(&attestation_descriptor);
    if (relocated_attestation < 0
        || bind_descriptor(relocated_runner, RUNNER_DESCRIPTOR, 0) != 0
        || bind_descriptor(relocated_attestation, ATTESTATION_DESCRIPTOR, 0) != 0
        || bind_descriptor(relocated_manifest, MANIFEST_DESCRIPTOR, 0) != 0
        || bind_descriptor(
            relocated_preregistration,
            PREREGISTRATION_DESCRIPTOR,
            0
        ) != 0
        || bind_descriptor(
            relocated_python,
            PYTHON_EXEC_DESCRIPTOR,
            1
        ) != 0
        || verify_fixed_attestation_descriptor(attestation->length) != 0
        || lseek(RUNNER_DESCRIPTOR, 0, SEEK_SET) != 0
        || lseek(MANIFEST_DESCRIPTOR, 0, SEEK_SET) != 0
        || lseek(PREREGISTRATION_DESCRIPTOR, 0, SEEK_SET) != 0
        || verify_fixed_private_descriptor(RUNNER_DESCRIPTOR) != 0
        || verify_fixed_private_descriptor(MANIFEST_DESCRIPTOR) != 0
        || verify_fixed_private_descriptor(PREREGISTRATION_DESCRIPTOR) != 0
        || fcntl(PYTHON_EXEC_DESCRIPTOR, F_GETFD) != FD_CLOEXEC) {
        goto cleanup;
    }
    if (close_relocated_descriptor(&relocated_python) != 0
        || close_relocated_descriptor(&relocated_runner) != 0
        || close_relocated_descriptor(&relocated_attestation) != 0
        || close_relocated_descriptor(&relocated_manifest) != 0
        || close_relocated_descriptor(&relocated_preregistration) != 0) {
        goto cleanup;
    }
    if (mark_all_ambient_descriptors_close_on_exec() != 0) {
        goto cleanup;
    }
    if (require_path_absent(expected->plan.pycache_prefix) != 0) {
        goto cleanup;
    }

    child_arguments[0] = expected->plan.python_argv0;
    child_arguments[1] = PYTHON_COMBINED_FLAGS;
    child_arguments[2] = PYTHON_XOPTION_FLAG;
    child_arguments[3] = pycache_argument;
    child_arguments[4] = "/proc/self/fd/3";
    child_arguments[5] = "--preregistration";
    child_arguments[6] = (char *)roles->preregistration->path;
    child_arguments[7] = "--expected-preregistration-sha256";
    child_arguments[8] = preregistration_tagged;
    child_arguments[9] = "--output-dir";
    child_arguments[10] = expected->plan.output_path;
    child_arguments[11] = NULL;
    cur0s_platform_execveat(
        PYTHON_EXEC_DESCRIPTOR,
        "",
        child_arguments,
        child_environment,
        AT_EMPTY_PATH
    );
    reject("launch_execveat_failed");

cleanup:
    close_relocated_descriptor(&relocated_python);
    close_relocated_descriptor(&relocated_runner);
    close_relocated_descriptor(&relocated_attestation);
    close_relocated_descriptor(&relocated_manifest);
    close_relocated_descriptor(&relocated_preregistration);
    if (attestation_descriptor >= 0) {
        close(attestation_descriptor);
    }
    close(RUNNER_DESCRIPTOR);
    close(ATTESTATION_DESCRIPTOR);
    close(MANIFEST_DESCRIPTOR);
    close(PREREGISTRATION_DESCRIPTOR);
    close(PYTHON_EXEC_DESCRIPTOR);
    return -1;
}
#endif

#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
static int parse_test_descriptor(const char *value, int *result) {
    uint64_t parsed;

    if (parse_decimal_u64(value, &parsed) != 0 || parsed > INT_MAX) {
        return reject("test_between_pass_descriptor_invalid");
    }
    *result = (int)parsed;
    return 0;
}

static int test_between_pass_barrier(void) {
    const char *signal_value = getenv("CUR0S_PREFLIGHT_TEST_SIGNAL_FD");
    const char *resume_value = getenv("CUR0S_PREFLIGHT_TEST_RESUME_FD");
    char marker = '1';
    char acknowledgement;
    int signal_descriptor;
    int resume_descriptor;
    ssize_t transferred;

    if (signal_value == NULL && resume_value == NULL) {
        return 0;
    }
    if (signal_value == NULL || resume_value == NULL
        || parse_test_descriptor(signal_value, &signal_descriptor) != 0
        || parse_test_descriptor(resume_value, &resume_descriptor) != 0) {
        return reject("test_between_pass_barrier_invalid");
    }
    do {
        transferred = write(signal_descriptor, &marker, 1U);
    } while (transferred < 0 && errno == EINTR);
    if (transferred != 1) {
        return reject("test_between_pass_signal_failed");
    }
    do {
        transferred = read(resume_descriptor, &acknowledgement, 1U);
    } while (transferred < 0 && errno == EINTR);
    if (transferred != 1 || acknowledgement != '1') {
        return reject("test_between_pass_resume_failed");
    }
    return 0;
}
#else
static int test_between_pass_barrier(void) {
    return 0;
}
#endif

static const char *operation_mode_name(operation_mode mode) {
    if (mode == MODE_LAUNCH) {
        return "launch";
    }
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    if (mode == MODE_TEST_LAUNCH_PLAN) {
        return "test_launch_plan";
    }
#endif
    return "verify_only";
}

static void emit_rejection(int usage_error, operation_mode mode) {
    fprintf(
        stderr,
        "{\"schema_version\":\"cur0s_native_preflight_result_v1\","
        "\"status\":\"rejected\",\"error\":\"%s\","
        "\"mode\":\"%s\",\"persistent_writes\":false,"
        "\"security_ceiling\":\"%s\"}\n",
        error_code == NULL
            ? (usage_error ? "usage_invalid" : "verification_failed")
            : error_code,
        operation_mode_name(mode),
        SECURITY_CEILING
    );
}

static int parse_arguments(
    int argument_count,
    char **arguments,
    arguments_config *config
) {
    int mode_seen = 0;
    int manifest_seen = 0;
    int digest_seen = 0;
    int preregistration_digest_seen = 0;

    memset(config, 0, sizeof(*config));
    config->mode = MODE_VERIFY_ONLY;

    for (int index = 1; index < argument_count; ++index) {
        if (strcmp(arguments[index], "--verify-only") == 0 && !mode_seen) {
            config->mode = MODE_VERIFY_ONLY;
            mode_seen = 1;
        } else if (strcmp(arguments[index], "--launch") == 0 && !mode_seen) {
            config->mode = MODE_LAUNCH;
            mode_seen = 1;
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
        } else if (strcmp(arguments[index], "--test-launch-plan") == 0
                   && !mode_seen) {
            config->mode = MODE_TEST_LAUNCH_PLAN;
            mode_seen = 1;
#endif
        } else if (strcmp(arguments[index], "--manifest") == 0
                   && !manifest_seen && index + 1 < argument_count) {
            config->manifest_path = arguments[++index];
            manifest_seen = 1;
        } else if (strcmp(arguments[index], "--manifest-sha256") == 0
                   && !digest_seen && index + 1 < argument_count) {
            if (parse_sha256(arguments[++index], config->manifest_digest) != 0) {
                return -1;
            }
            digest_seen = 1;
        } else if (strcmp(
                       arguments[index],
                       "--expected-preregistration-sha256"
                   ) == 0
                   && !preregistration_digest_seen
                   && index + 1 < argument_count) {
            if (parse_sha256(
                    arguments[++index],
                    config->expected_preregistration_digest
                ) != 0) {
                return -1;
            }
            preregistration_digest_seen = 1;
        } else {
            return reject("usage_invalid");
        }
    }
    if (!mode_seen || !manifest_seen || !digest_seen
        || !canonical_absolute_path(config->manifest_path)
        || (config->mode == MODE_VERIFY_ONLY && preregistration_digest_seen)
        || (config->mode != MODE_VERIFY_ONLY && !preregistration_digest_seen)) {
        return reject("usage_invalid");
    }
    config->expected_preregistration_digest_present = preregistration_digest_seen;
    return 0;
}

int main(int argument_count, char **arguments) {
    arguments_config config;
    observation first_manifest_observation;
    observation final_manifest_observation;
    observation *first_observations;
    observation second_observation;
    manifest expected;
    char *manifest_payload;
    char *final_manifest_payload;
    size_t manifest_bytes;
    size_t final_manifest_bytes;
    launch_roles roles;
    held_launch_descriptors held;
    native_map_snapshot earliest_maps;
    text_buffer native_maps;
    text_buffer attestation;
    int maps_capture_status;
    int exit_status;

    maps_capture_status = capture_earliest_native_maps(
        argument_count,
        arguments,
        &earliest_maps
    );
    memset(&config, 0, sizeof(config));
    config.mode = MODE_VERIFY_ONLY;
    first_observations = NULL;
    memset(&expected, 0, sizeof(expected));
    manifest_payload = NULL;
    final_manifest_payload = NULL;
    manifest_bytes = 0U;
    final_manifest_bytes = 0U;
    memset(&roles, 0, sizeof(roles));
    held.python_descriptor = -1;
    held.runner_descriptor = -1;
    held.manifest_descriptor = -1;
    held.preregistration_descriptor = -1;
    memset(&native_maps, 0, sizeof(native_maps));
    memset(&attestation, 0, sizeof(attestation));
    exit_status = 1;

#if defined(CUR0S_COMPILE_ANDROID_LAUNCH) && !defined(__ANDROID__)
    (void)&execute_android_launch;
#endif

    if (maps_capture_status != 0) {
        emit_rejection(0, config.mode);
        return 1;
    }
    if (parse_arguments(argument_count, arguments, &config) != 0) {
        emit_rejection(1, config.mode);
        return 2;
    }
#if !defined(__ANDROID__)
    if (config.mode == MODE_LAUNCH) {
        reject("launch_requires_android_api30");
        emit_rejection(0, config.mode);
        return 1;
    }
#endif
    if (config.mode != MODE_VERIFY_ONLY
        && observe_empty_outer_environment(&config) != 0) {
        emit_rejection(0, config.mode);
        return 1;
    }
    if (read_manifest(
            config.manifest_path,
            config.manifest_digest,
            &manifest_payload,
            &manifest_bytes,
            &first_manifest_observation
        ) != 0
        || parse_manifest_payload(manifest_payload, manifest_bytes, &expected) != 0) {
        goto cleanup;
    }
    first_observations = calloc(expected.count, sizeof(*first_observations));
    if (first_observations == NULL) {
        reject("memory_allocation_failed");
        goto cleanup;
    }
    for (size_t index = 0; index < expected.count; ++index) {
        if (verify_entry(&expected.entries[index], &first_observations[index]) != 0) {
            goto cleanup;
        }
    }
    if (test_between_pass_barrier() != 0) {
        goto cleanup;
    }
    for (size_t index = 0; index < expected.count; ++index) {
        if (verify_entry(&expected.entries[index], &second_observation) != 0) {
            goto cleanup;
        }
        if (!observations_equal(&first_observations[index], &second_observation)) {
            reject("entry_changed_between_passes");
            goto cleanup;
        }
    }
    if (read_manifest(
            config.manifest_path,
            config.manifest_digest,
            &final_manifest_payload,
            &final_manifest_bytes,
            &final_manifest_observation
        ) != 0) {
        goto cleanup;
    }
    if (!observations_equal(
            &first_manifest_observation,
            &final_manifest_observation
        ) || manifest_bytes != final_manifest_bytes) {
        reject("manifest_changed_between_passes");
        goto cleanup;
    }
    if (bind_earliest_native_maps_to_manifest(
            &earliest_maps,
            &expected,
            first_observations
        ) != 0
        || build_native_maps_identity(
            &earliest_maps,
            &expected,
            &native_maps
        ) != 0) {
        goto cleanup;
    }
    if (config.mode == MODE_VERIFY_ONLY) {
        char manifest_hex[CUR0S_SHA256_HEX_BYTES + 1U];

        cur0s_sha256_hex(config.manifest_digest, manifest_hex);
        printf(
            "{\"schema_version\":\"cur0s_native_preflight_result_v1\","
            "\"status\":\"verified\",\"mode\":\"verify_only\","
            "\"manifest_sha256\":\"sha256:%s\",\"entries_verified\":%zu,"
            "\"passes_completed\":2,\"persistent_writes\":false,"
            "\"security_ceiling\":\"%s\"}\n",
            manifest_hex,
            expected.count,
            SECURITY_CEILING
        );
        exit_status = 0;
        goto cleanup;
    }
    if (collect_launch_roles(&expected, &config, &roles) != 0
        || prepare_held_launch_descriptors(
            &expected,
            &roles,
            first_observations,
            &config,
            &final_manifest_observation,
            arguments[0],
            &held
        ) != 0
        || build_native_attestation(
            &expected,
            &roles,
            &config,
            &native_maps,
            &attestation
        ) != 0) {
        goto cleanup;
    }
#if defined(CUR0S_NATIVE_PREFLIGHT_TESTING) \
    && CUR0S_NATIVE_PREFLIGHT_TESTING == 1
    if (config.mode == MODE_TEST_LAUNCH_PLAN) {
        if (emit_test_launch_plan(
                &expected,
                &roles,
                &config,
                &attestation
            ) != 0) {
            goto cleanup;
        }
        exit_status = 0;
        goto cleanup;
    }
#endif
#if defined(__ANDROID__)
    if (execute_android_launch(
            &expected,
            &roles,
            &config,
            &held,
            &attestation
        ) != 0) {
        goto cleanup;
    }
#else
    reject("launch_requires_android_api30");
    goto cleanup;
#endif

cleanup:
    if (exit_status != 0) {
        emit_rejection(0, config.mode);
    }
    close_held_launch_descriptors(&held);
    free_text_buffer(&native_maps);
    free_text_buffer(&attestation);
    free(first_observations);
    free(manifest_payload);
    free(final_manifest_payload);
    free_manifest(&expected);
    return exit_status;
}
