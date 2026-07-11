"""Governed Adreno OpenCL fallback for the Gemma 4 E4B packed INT2 LM head.

This module is control-plane code only.  It freezes and validates the exact
phone-native OpenCL experiment without ever reading candidate logits on the
orchestration host.  The phone runner imports the conversion and metric helpers
so the preregistration and execution paths share one fail-closed contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import stat
import struct
import subprocess
import sys
import tempfile
from typing import Any

PREREGISTRATION_SCHEMA = "gemma4_e4b_adreno_int2_lm_head_preregistration_v1"
OPENCL_CONTRACT_SCHEMA = "gemma4_e4b_adreno_opencl_execution_contract_v1"
PHONE_RECEIPT_SCHEMA = "gemma4_e4b_adreno_int2_lm_head_phone_receipt_v1"
SOURCE_NEUTRAL_PREFLIGHT_SCHEMA = "gemma4_e4b_adreno_source_neutral_preflight_v1"
SOURCE_NEUTRAL_PREFLIGHT_COMPLETION_SCHEMA = (
    "gemma4_e4b_adreno_preflight_completion_v1"
)
ADB_PREFLIGHT_CUSTODY_SCHEMA = (
    "gemma4_e4b_adreno_adb_forwarded_ssh_custody_receipt_v2"
)
ADB_PREFLIGHT_CUSTODY_COMPLETION_SCHEMA = (
    "gemma4_e4b_adreno_adb_forwarded_ssh_custody_completion_v2"
)
AUTHORIZED_ADB_SERIAL = "FY25013101C8"
AUTHORIZED_ADB_FORWARD_LOCAL = "tcp:18022"
AUTHORIZED_ADB_FORWARD_REMOTE = "tcp:8022"
AUTHORIZED_TERMUX_SSH_ALIAS = "redmagic-termux-polymath"
AUTHORIZED_TERMUX_SSH_HOST = "127.0.0.1"
AUTHORIZED_TERMUX_SSH_PORT = 18_022
AUTHORIZED_TERMUX_SSH_USER = "u0_a536"
AUTHORIZED_TERMUX_SSH_IDENTITY_FILE = (
    "/Users/prinivenpillay/.ssh/polymath_host"
)
AUTHORIZED_TERMUX_SSH_KNOWN_HOSTS_FILE = (
    "/Users/prinivenpillay/.ssh/known_hosts"
)
AUTHORIZED_TERMUX_SSH_SERVER_KEY_FINGERPRINT = (
    "SHA256:RK4COBqnfndb+gOOFkaCMNOHDV0AxQkhx94X1yW+tgs"
)
AUTHORIZED_TERMUX_SSH_CLIENT_KEY_FINGERPRINT = (
    "SHA256:gKxDEgEScPrY8O3omM8WWAG3Hwo2cCyq13demaGw3bY"
)
AUTHORIZED_TERMUX_SSH_REQUIRED_OVERRIDES = (
    "-T",
    "-o",
    "BatchMode=yes",
    "-o",
    "PasswordAuthentication=no",
    "-o",
    "KbdInteractiveAuthentication=no",
    "-o",
    "NumberOfPasswordPrompts=0",
    "-o",
    "RequestTTY=no",
    "-o",
    "StrictHostKeyChecking=yes",
    "-o",
    "IdentitiesOnly=yes",
)
AUTHORIZED_TERMUX_UID = 10_536
AUTHORIZED_TERMUX_GID = 10_536
CANDIDATE_ID = (
    "adreno_opencl_direct_packed_w2_scalar_bf16_product_fp32_tree_bf16_rne_v1"
)
S16_FALSIFICATION_SCHEMA = "gemma4_e4b_l2_int16_v2_oracle_falsification_report_v1"
S16_CANDIDATE_ID = "w2_s16_activation_bw2_weight_bf16_rne_scale_s16_output_2m10_v2"
FROZEN_FRONTIER_SELECTOR_SHA256 = (
    "a3ab8f26d5c794e2235a65a93cfc5b4eea7a40d479d9d83be34fabf2ee4a9647"
)
FROZEN_OPENCL_EVIDENCE_SHA256 = (
    "6b0605334c085a4fe7f404ff0723ffe295283796e1048dfdbfdda1bf5a2fe3a2"
)
FROZEN_S16_FALSIFICATION_SHA256 = (
    "44ba89a8ff760d89d05e5ddd2146b2e584f99496ca25fe81091361372bcc5e59"
)
S16_ORACLE_GATE_SHA256 = (
    "aa063f64473de95fdd3208995a51dd314f0e4947c78adc1826a2358ea65693b1"
)
FROZEN_PARENT_FRONTIER_ROOT_SHA256 = (
    "bb045f0761405b521705609d473fa1cb7b504634197256b2b684c061e1fc4d78"
)
FROZEN_PARENT_CAPSULE_SHA256 = (
    "66072e0dee357c9d7c178c3fa3628a6230fa5992659325b80e7eefa6e4dbdd2b"
)

INPUT_FEATURES = 2_560
OUTPUT_FEATURES = 262_144
PACKED_BYTES_PER_ROW = INPUT_FEATURES // 4
PACKED_WEIGHT_BYTES = OUTPUT_FEATURES * PACKED_BYTES_PER_ROW
SCALE_F32_BYTES = OUTPUT_FEATURES * 4
SCALE_BF16_BYTES = OUTPUT_FEATURES * 2
INPUT_BYTES = INPUT_FEATURES * 2
OUTPUT_BYTES = OUTPUT_FEATURES * 2
LOCAL_SIZE = 64
ROWS_PER_WORKGROUP = 8
WORKGROUP_COUNT = OUTPUT_FEATURES // ROWS_PER_WORKGROUP
DISPATCH_COUNT = 8
REPLAY_COUNT_PER_CASE = 2

MODEL_BYTES = 3_525_094_516
MODEL_SHA256 = "391946da2e0bec22288e9fe50a4d31d2401c9570ba3baaf0ba43d644dadeb1d4"
MODEL_REVISION = "9a78a5adac7bca7a9e421634e4b58f41ca7cbca3"
MODEL_REPOSITORY = "google/gemma-4-E4B-it-qat-mobile-transformers"
SCALE_ABSOLUTE_OFFSET = 418_624
PACKED_WEIGHT_ABSOLUTE_OFFSET = 433_630_324
PACKED_WEIGHT_SHA256 = (
    "4733d4ef634f781c7b4094e0df6c432b53e3390e161d546951ea6806de9e0d07"
)
SCALE_F32_SHA256 = "870e405117e2b9b91a86a4210dc66de2d46af52c9274ea46c3193dd69b437eb6"
SCALE_BF16_RNE_AS_F32_SHA256 = (
    "489f4400faaf5f20984bc798d2e1ca581aaf7237e1f37cb6ce505df747e01633"
)
ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256 = (
    "fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f"
)
VENDOR_RUNTIME_FILES = (
    {
        "role": "opencl_icd",
        "absolute_path": "/vendor/lib64/libOpenCL.so",
        "bytes": 87_504,
        "sha256": "cd35cf1ecbfb2053e45566421aa605f819b69ceb5264706ed4feb15bed0942f9",
    },
    {
        "role": "adreno_opencl_driver",
        "absolute_path": "/vendor/lib64/libOpenCL_adreno.so",
        "bytes": 200_392,
        "sha256": "7571bd91b0bb8cad06ce50873865c4161778aa0bf3d2af159a9098a5aa7497ac",
    },
    {
        "role": "adreno_opencl_compiler",
        "absolute_path": "/vendor/lib64/libadreno_compiler_cl.so",
        "bytes": 32_978_208,
        "sha256": "8102c13cd4dedbd26c0aeed63393d44c492879feffb09e2b4026d28f24dbd9fd",
    },
    {
        "role": "adreno_utils",
        "absolute_path": "/vendor/lib64/libadreno_utils.so",
        "bytes": 134_224,
        "sha256": "9616f5dddff3ac30e060950bc4a0f8a20763b4cf51b27bcd752df20d5523b28a",
    },
)
REQUIRED_RUNTIME_MAPPINGS = (
    "/vendor/lib64/libOpenCL.so",
    "/vendor/lib64/libOpenCL_adreno.so",
    "/vendor/lib64/libadreno_compiler_cl.so",
    "/vendor/lib64/libadreno_utils.so",
    "/system/lib64/libvndksupport.so",
    "/apex/com.android.runtime/lib64/bionic/libdl_android.so",
    "/system/lib64/liblog.so",
    "/system/lib64/libc++.so",
    "/apex/com.android.runtime/lib64/bionic/libc.so",
    "/apex/com.android.runtime/lib64/bionic/libdl.so",
    "/apex/com.android.runtime/lib64/bionic/libm.so",
    "/data/data/com.termux/files/usr/lib/libc++_shared.so",
)
TERMUX_CLANGXX_PATH = "/data/data/com.termux/files/usr/bin/clang++"
TERMUX_CLANGXX_LINK_TARGET = "clang-21"
TERMUX_CLANGXX_RESOLVED_PATH = "/data/data/com.termux/files/usr/bin/clang-21"
TERMUX_CLANGXX_RESOLVED_BYTES = 120_848
TERMUX_CLANGXX_RESOLVED_SHA256 = (
    "34da8e3a9b71793eb70c25670e1fe2bce4d37f1e2837ba8dc0c516c2ca0ffc83"
)
TERMUX_CLANGXX_VERSION_STDOUT_SHA256 = (
    "ba8cc9283b3d1015d7534124eee8908cc5e9b42955e66d10f27a86009c8e76c1"
)
TERMUX_LLD_PATH = "/data/data/com.termux/files/usr/bin/ld.lld"
TERMUX_LLD_LINK_TARGET = "lld"
TERMUX_LLD_RESOLVED_PATH = "/data/data/com.termux/files/usr/bin/lld"
TERMUX_LLD_RESOLVED_BYTES = 5_615_720
TERMUX_LLD_RESOLVED_SHA256 = (
    "5214b9511221a87e02c4a9603f470dd83804a54f4cf62475f168d47d707d964d"
)
TERMUX_LLD_VERSION_STDOUT_SHA256 = (
    "418d72df86baf70c88b9a96a9118e3cdc66be0537a58f66a6879df0479f9a78f"
)
TERMUX_CLANG_CPP_PATH = "/data/data/com.termux/files/usr/lib/libclang-cpp.so"
TERMUX_CLANG_CPP_BYTES = 59_130_224
TERMUX_CLANG_CPP_SHA256 = (
    "279758cd28398a44d0f036474ccd4839e1ba0c44bcbfc44cdb05a28527b0227d"
)
TERMUX_LLVM_PATH = "/data/data/com.termux/files/usr/lib/libLLVM.so"
TERMUX_LLVM_BYTES = 129_366_048
TERMUX_LLVM_SHA256 = (
    "d8157ef272769f24142408f819e9eb27139e9c3b0fecbd468fe5416e77c402ce"
)
TERMUX_COMPILER_RUNTIME_FILES = (
    {
        "entry_absolute_path": TERMUX_CLANG_CPP_PATH,
        "symlink_target": None,
        "resolved_absolute_path": TERMUX_CLANG_CPP_PATH,
        "bytes": TERMUX_CLANG_CPP_BYTES,
        "sha256": TERMUX_CLANG_CPP_SHA256,
    },
    {
        "entry_absolute_path": TERMUX_LLVM_PATH,
        "symlink_target": None,
        "resolved_absolute_path": TERMUX_LLVM_PATH,
        "bytes": TERMUX_LLVM_BYTES,
        "sha256": TERMUX_LLVM_SHA256,
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libffi.so",
        "symlink_target": None,
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libffi.so",
        "bytes": 86_144,
        "sha256": "11cfbf6e8a9d18ebc7dd4f5a1acb08404b1dea9503e5ca13066d1b0fa01435e1",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libz.so.1",
        "symlink_target": "libz.so.1.3.2",
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libz.so.1.3.2",
        "bytes": 72_232,
        "sha256": "6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libzstd.so.1",
        "symlink_target": "libzstd.so.1.5.7",
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libzstd.so.1.5.7",
        "bytes": 820_840,
        "sha256": "5baa1d62cdd945afb01ae0a8d4ee8cdd3bcb8ec4d21e90b30ef017655a86bebf",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libxml2.so.16",
        "symlink_target": "libxml2.so.16.1.3",
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libxml2.so.16.1.3",
        "bytes": 1_048_952,
        "sha256": "541f9a23a573322ffd6f31f2f28af0c4f614bfb547441006c15ddc0192f35366",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libicuuc.so.78",
        "symlink_target": "libicuuc.so.78.3",
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libicuuc.so.78.3",
        "bytes": 1_867_696,
        "sha256": "104dc1ed87acd79b200cac3998bbfcdcc02cc01d139f5c58a8c8d363b4f6d49d",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libiconv.so",
        "symlink_target": None,
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libiconv.so",
        "bytes": 1_082_512,
        "sha256": "763c461c53d47e4f10b585b33ed6589949ce7765aa560f4b2aedfc7e4885cae2",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libicudata.so.78",
        "symlink_target": "libicudata.so.78.3",
        "resolved_absolute_path": "/data/data/com.termux/files/usr/lib/libicudata.so.78.3",
        "bytes": 33_108_952,
        "sha256": "82b40055d3f2eada13b5816069c5bc2d82a4fa5b919fad4f69b1e83f5382ec7a",
    },
)
TERMUX_LIBCXX_PATH = "/data/data/com.termux/files/usr/lib/libc++_shared.so"
TERMUX_LIBCXX_BYTES = 1_374_336
TERMUX_LIBCXX_SHA256 = (
    "e09c2f45cf4cf8ae574f94b6c2650d99ead0d332d5396f6613f062a2d2d73540"
)
TERMUX_PYTHON_PATH = "/data/data/com.termux/files/usr/bin/python3"
TERMUX_PYTHON_LINK_TARGET = "python3.13"
TERMUX_PYTHON_RESOLVED_PATH = "/data/data/com.termux/files/usr/bin/python3.13"
TERMUX_PYTHON_RESOLVED_BYTES = 4_728
TERMUX_PYTHON_RESOLVED_SHA256 = (
    "1d3987c39c03b764d629a8c8c6fdc5979d8f8e28beb7193f312fc39d63b70404"
)
TERMUX_PYTHON_VERSION = "3.13.13"
TERMUX_PYTHON_RUNTIME_FILES = (
    {
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libpython3.13.so"
        ),
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libpython3.13.so"
        ),
        "bytes": 5_153_728,
        "sha256": "7ca4f4f00ae2e1afde50bb3ce01926ec6edb582719c7731a416235833d4d2319",
    },
    {
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libandroid-posix-semaphore.so"
        ),
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libandroid-posix-semaphore.so"
        ),
        "bytes": 7_136,
        "sha256": "adc7a3aa24f7e3baadc6149dea370bceeb11f058f19e22d8ca46e19f19e9e803",
    },
    {
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libbz2.so.1.0"
        ),
        "symlink_target": "libbz2.so.1.0.8",
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libbz2.so.1.0.8"
        ),
        "bytes": 50_328,
        "sha256": "5129a738fec8c6733954fa6a98f1fad9538e818f38db89d5391f12e5657746dc",
    },
    {
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libcrypto.so.3"
        ),
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libcrypto.so.3"
        ),
        "bytes": 4_611_704,
        "sha256": "28534a11feb019f149032374c88d1c52f87baa241bc9ee7ab0bb1f3d24d21118",
    },
    {
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/liblzma.so.5"
        ),
        "symlink_target": "liblzma.so.5.8.3",
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/liblzma.so.5.8.3"
        ),
        "bytes": 157_112,
        "sha256": "f8ab7f7548a57222c1115274bd6ff10d08917ba0701c1b3892be5a12a8d506cf",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libffi.so",
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libffi.so"
        ),
        "bytes": 86_144,
        "sha256": "11cfbf6e8a9d18ebc7dd4f5a1acb08404b1dea9503e5ca13066d1b0fa01435e1",
    },
    {
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libz.so.1",
        "symlink_target": "libz.so.1.3.2",
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libz.so.1.3.2"
        ),
        "bytes": 72_232,
        "sha256": "6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef",
    },
)
TERMUX_PYTHON_STDLIB_DIR = "/data/data/com.termux/files/usr/lib/python3.13"
TERMUX_PYTHON_STDLIB_TREE_IDENTITY = {
    "entry_count": 12_080,
    "regular_bytes": 232_330_107,
    "root_sha256": "3de0e05e7f6098c4624bae415f01303b99e0675b85e819a5738a518a4d9e7c6d",
}
TERMUX_CLANG_RESOURCE_DIR = "/data/data/com.termux/files/usr/lib/clang/21"
TERMUX_CLANG_RESOURCE_TREE_IDENTITY = {
    "entry_count": 330,
    "regular_bytes": 49_574_163,
    "root_sha256": "ffdceb85df6a46d5b43d1cabea2e36b984e2d30143fc639ed01bee9cacdff854",
}
TERMUX_INCLUDE_DIR = "/data/data/com.termux/files/usr/include"
TERMUX_INCLUDE_TREE_IDENTITY = {
    "entry_count": 10_906,
    "regular_bytes": 134_436_489,
    "root_sha256": "e951f4e4eeebfb1ae61af0b05337bb12ce800a398a62476b21ffeb10f6fd4c1d",
}
TERMUX_LINK_INPUT_FILES = (
    {
        "role": "crt_begin",
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/crtbegin_dynamic.o"
        ),
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/crtbegin_dynamic.o"
        ),
        "bytes": 3_896,
        "sha256": "612cf67a324667367e78f99c4f42116d9f0ae94dd1bed72303c0b989d87facac",
    },
    {
        "role": "crt_end",
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/crtend_android.o"
        ),
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/crtend_android.o"
        ),
        "bytes": 832,
        "sha256": "4a73856c6b87bfaa7b6fc5963796f21941f85f9bb3de36f688f70b5c5ceca44b",
    },
    {
        "role": "unwind_archive",
        "entry_absolute_path": "/data/data/com.termux/files/usr/lib/libunwind.a",
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/libunwind.a"
        ),
        "bytes": 92_452,
        "sha256": "c52c8462134a1610e93d873e9d992f4804027d0c73115b2ea4c21b0aed5cbe65",
    },
    {
        "role": "clang_rt_builtins",
        "entry_absolute_path": (
            "/data/data/com.termux/files/usr/lib/clang/21/lib/linux/"
            "libclang_rt.builtins-aarch64-android.a"
        ),
        "symlink_target": None,
        "resolved_absolute_path": (
            "/data/data/com.termux/files/usr/lib/clang/21/lib/linux/"
            "libclang_rt.builtins-aarch64-android.a"
        ),
        "bytes": 409_982,
        "sha256": "9aeed0613b933c2c79a7c366371b5910681b740b78093d33237fd31c67345cb2",
    },
    {
        "role": "bionic_libdl",
        "entry_absolute_path": "/system/lib64/libdl.so",
        "symlink_target": "/apex/com.android.runtime/lib64/bionic/libdl.so",
        "resolved_absolute_path": (
            "/apex/com.android.runtime/lib64/bionic/libdl.so"
        ),
        "bytes": 50_760,
        "sha256": "7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479",
    },
    {
        "role": "bionic_libm",
        "entry_absolute_path": "/system/lib64/libm.so",
        "symlink_target": "/apex/com.android.runtime/lib64/bionic/libm.so",
        "resolved_absolute_path": (
            "/apex/com.android.runtime/lib64/bionic/libm.so"
        ),
        "bytes": 249_192,
        "sha256": "2a99c9ac7a12461663ec31b8d4ee3404ee99a1dca53f7c30b248bcccb155eefc",
    },
    {
        "role": "bionic_libc",
        "entry_absolute_path": "/system/lib64/libc.so",
        "symlink_target": "/apex/com.android.runtime/lib64/bionic/libc.so",
        "resolved_absolute_path": (
            "/apex/com.android.runtime/lib64/bionic/libc.so"
        ),
        "bytes": 1_143_072,
        "sha256": "b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf",
    },
)
PHONE_SYSTEM_RUNTIME_FILES = (
    {
        "role": "vndk_support",
        "entry_absolute_path": "/system/lib64/libvndksupport.so",
        "symlink_target": None,
        "resolved_absolute_path": "/system/lib64/libvndksupport.so",
        "bytes": 51_352,
        "sha256": "3ce8b48aa76739ad3a8668dc8fc0ce462151a984b4a6bd881aa473f4f09fc179",
    },
    {
        "role": "vndk_dl_android",
        "entry_absolute_path": "/system/lib64/libdl_android.so",
        "symlink_target": (
            "/apex/com.android.runtime/lib64/bionic/libdl_android.so"
        ),
        "resolved_absolute_path": (
            "/apex/com.android.runtime/lib64/bionic/libdl_android.so"
        ),
        "bytes": 34_664,
        "sha256": "10370703f28cb1aebc12f30cec1e6e3940e65975495e01c69642f29195b31adc",
    },
    {
        "role": "android_log",
        "entry_absolute_path": "/system/lib64/liblog.so",
        "symlink_target": None,
        "resolved_absolute_path": "/system/lib64/liblog.so",
        "bytes": 101_848,
        "sha256": "b9d6a5f515686068e0a66d3d56c248701745f59273b20051a62bec4d44bedd9e",
    },
    {
        "role": "android_libcxx",
        "entry_absolute_path": "/system/lib64/libc++.so",
        "symlink_target": None,
        "resolved_absolute_path": "/system/lib64/libc++.so",
        "bytes": 1_083_168,
        "sha256": "794eb8fafd7be35da3725e9ec0b15189c6f4f2544f5b78afd8a647dde5b69195",
    },
    {
        "role": "android_netd_client_control_plane_transitive",
        "entry_absolute_path": "/system/lib64/libnetd_client.so",
        "symlink_target": None,
        "resolved_absolute_path": "/system/lib64/libnetd_client.so",
        "bytes": 52_368,
        "sha256": "d4aedc713a2d6f06214faa6c27ea333909a685a717d12b5a750d134ec4733c89",
    },
)
TERMUX_EXEC_INTERPOSER_PATH = (
    "/data/data/com.termux/files/usr/lib/libtermux-exec.so"
)
TERMUX_EXEC_INTERPOSER_BYTES = 13_808
TERMUX_EXEC_INTERPOSER_SHA256 = (
    "45ad0183d4fdb399ce5df0823b1d67b53a01bbb2596c7e4db79b7c255214c9c8"
)
TERMUX_EXEC_INTERPOSER_MODE = 0o700
TERMUX_EXEC_INTERPOSER_UID = 10_536
TERMUX_EXEC_INTERPOSER_GID = 10_536
ANDROID_LINKER64_PATH = "/system/bin/linker64"
ANDROID_LINKER64_LINK_TARGET = "/apex/com.android.runtime/bin/linker64"
ANDROID_LINKER64_RESOLVED_PATH = "/apex/com.android.runtime/bin/linker64"
ANDROID_LINKER64_RESOLVED_BYTES = 2_160_952
ANDROID_LINKER64_RESOLVED_SHA256 = (
    "6aa1b8bcf1da7e8b48f67f78eebaa2d9356c76ad3c9809bd5576b579907d7f9e"
)
NATIVE_BUILD_ARGUMENTS = (
    "--driver-mode=g++",
    "--no-default-config",
    "--target=aarch64-linux-android35",
    f"-resource-dir={TERMUX_CLANG_RESOURCE_DIR}",
    f"--ld-path={TERMUX_LLD_PATH}",
    "-std=c++20",
    "-O3",
    "-DNDEBUG",
    "-fvisibility=hidden",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Wshadow",
    "-Wconversion",
    "-Wsign-conversion",
    "-Werror",
)

REQUIRED_DEVICE_EXTENSIONS = (
    "cl_khr_subgroups",
    "cl_qcom_bfloat16_product",
)
OPENCL_DEVICE_EXTENSIONS_BYTES = 1_583
OPENCL_DEVICE_EXTENSIONS_SHA256 = (
    "17ee35214eed83330ea64b7b5e476d75bf916e4700da047b024afafbee328b23"
)

SENTINEL_CASE_ID = "off_s16_lattice_bf16_0x3a80"
SENTINEL_INPUT_SHA256 = (
    "8caaaaa8532593127a04ee96fca610df3fc17b44d51e72e5117f5451a94857d6"
)

FROZEN_THRESHOLDS: dict[str, Any] = {
    "max_abs": 0.1875,
    "rms": 0.03,
    "relative_l2": 0.0075,
    "cosine_min": 0.99998,
    "softmax_js_divergence_max": 2.0e-6,
    "top_k_set_overlap_min": 0.9375,
    "top_1_equal": True,
}

FROZEN_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "structured_dynamic",
        "s16_source_relative_path": (
            "inputs/gemma4_e4b_f5_w2_lm_head.structured_dynamic.s16.raw"
        ),
        "s16_source_sha256": (
            "360e7c9f22a0dbb0c135b3a1b696d206e66d02b57b6320eb3e8210d1e880e236"
        ),
        "bf16_input_sha256": (
            "5cca991319c94de485360d2b05b87a80b9b88bc3fe636c8a478ccda9461bada8"
        ),
        "authority_relative_path": (
            "references/structured_dynamic.w2_qat_authority.bf16.raw"
        ),
        "authority_sha256": (
            "30e624bdbad91be77ef6f3d18d46eef2cec6dc5b7a23e7fb4438bf74ae54a30a"
        ),
    },
    {
        "case_id": "balanced_splitmix64",
        "s16_source_relative_path": (
            "inputs/gemma4_e4b_f5_w2_lm_head.balanced_splitmix64.s16.raw"
        ),
        "s16_source_sha256": (
            "8ac246d9328dca16ae2c182906bdb11b8080f0dc71161d28838291eb27f1bf90"
        ),
        "bf16_input_sha256": (
            "2065c350db9e1b835193f7b369b4561bae099eb20931562bede7687727af16aa"
        ),
        "authority_relative_path": (
            "references/balanced_splitmix64.w2_qat_authority.bf16.raw"
        ),
        "authority_sha256": (
            "4d61ad4b4c98089646a6c11e825fb7486090c94fba376d6de1c0a5127c20e26a"
        ),
    },
    {
        "case_id": "low_amplitude_splitmix64",
        "s16_source_relative_path": (
            "inputs/gemma4_e4b_f5_w2_lm_head.low_amplitude_splitmix64.s16.raw"
        ),
        "s16_source_sha256": (
            "05b0526761aa7a5c83156a6bcdf3954a784b23d8b97ffc864e3acc963a3b490a"
        ),
        "bf16_input_sha256": (
            "0d0d93d4562b91ee90d129e0e7c277654659e27a7a87cbc4e4a62276e61dcbe3"
        ),
        "authority_relative_path": (
            "references/low_amplitude_splitmix64.w2_qat_authority.bf16.raw"
        ),
        "authority_sha256": (
            "9769af1ba2b21d3d7803f9bb139c17eb96c0ae0a893ef763b87060d3c68bebd2"
        ),
    },
)

NATIVE_BUILD_SOURCE_FILES = (
    "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.h",
    "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.cpp",
    "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp",
)
SOURCE_CLOSURE = (
    "polymath_ai/frontier/e4b_adreno_int2_lm_head.py",
    "scripts/host/build_e4b_adreno_int2_prereg.py",
    "scripts/host/run_e4b_adreno_int2_preflight_via_adb.py",
    "scripts/termux/run_e4b_adreno_int2_preflight.py",
    "scripts/termux/run_e4b_adreno_int2_phone_gate.py",
    *NATIVE_BUILD_SOURCE_FILES,
)
SOURCE_EXECUTABLES: frozenset[str] = frozenset()


class AdrenoGateError(RuntimeError):
    """Raised when the OpenCL candidate cannot preserve its frozen contract."""


def toolchain_contract() -> dict[str, Any]:
    """Return the exact phone compiler and exec-transport contract."""
    return {
        "compiler_path_class": "termux_prefix_bin_clangxx_exact_resolved_target",
        "compiler_symlink_absolute_path": TERMUX_CLANGXX_PATH,
        "compiler_symlink_target": TERMUX_CLANGXX_LINK_TARGET,
        "compiler_resolved_absolute_path": TERMUX_CLANGXX_RESOLVED_PATH,
        "compiler_resolved_bytes": TERMUX_CLANGXX_RESOLVED_BYTES,
        "compiler_resolved_sha256": TERMUX_CLANGXX_RESOLVED_SHA256,
        "compiler_version_stdout_sha256": TERMUX_CLANGXX_VERSION_STDOUT_SHA256,
        "arbitrary_CXX_override_allowed": False,
        "linker_symlink_absolute_path": TERMUX_LLD_PATH,
        "linker_symlink_target": TERMUX_LLD_LINK_TARGET,
        "linker_resolved_absolute_path": TERMUX_LLD_RESOLVED_PATH,
        "linker_resolved_bytes": TERMUX_LLD_RESOLVED_BYTES,
        "linker_resolved_sha256": TERMUX_LLD_RESOLVED_SHA256,
        "linker_version_stdout_sha256": TERMUX_LLD_VERSION_STDOUT_SHA256,
        "compiler_arguments": list(NATIVE_BUILD_ARGUMENTS),
        "native_build_source_files": list(NATIVE_BUILD_SOURCE_FILES),
        "cxx_runtime": {
            "absolute_path": TERMUX_LIBCXX_PATH,
            "bytes": TERMUX_LIBCXX_BYTES,
            "sha256": TERMUX_LIBCXX_SHA256,
            "soname": "libc++_shared.so",
        },
        "compiler_runtime_libraries": [
            dict(item) for item in TERMUX_COMPILER_RUNTIME_FILES
        ],
        "compiler_resource_tree": {
            "absolute_path": TERMUX_CLANG_RESOURCE_DIR,
            **TERMUX_CLANG_RESOURCE_TREE_IDENTITY,
        },
        "include_tree": {
            "absolute_path": TERMUX_INCLUDE_DIR,
            **TERMUX_INCLUDE_TREE_IDENTITY,
        },
        "link_input_files": [dict(item) for item in TERMUX_LINK_INPUT_FILES],
        "control_plane_python": {
            "entry_absolute_path": TERMUX_PYTHON_PATH,
            "symlink_target": TERMUX_PYTHON_LINK_TARGET,
            "resolved_absolute_path": TERMUX_PYTHON_RESOLVED_PATH,
            "resolved_bytes": TERMUX_PYTHON_RESOLVED_BYTES,
            "resolved_sha256": TERMUX_PYTHON_RESOLVED_SHA256,
            "version": TERMUX_PYTHON_VERSION,
            "required_flags": ["-I", "-S", "-B"],
            "exact_parent_environment": True,
            "runtime_files": [dict(item) for item in TERMUX_PYTHON_RUNTIME_FILES],
            "stdlib_tree": {
                "absolute_path": TERMUX_PYTHON_STDLIB_DIR,
                **TERMUX_PYTHON_STDLIB_TREE_IDENTITY,
            },
        },
        "termux_exec_interposer": {
            "source_absolute_path": TERMUX_EXEC_INTERPOSER_PATH,
            "source_bytes": TERMUX_EXEC_INTERPOSER_BYTES,
            "source_sha256": TERMUX_EXEC_INTERPOSER_SHA256,
            "source_mode_octal": "0700",
            "source_uid": TERMUX_EXEC_INTERPOSER_UID,
            "source_gid": TERMUX_EXEC_INTERPOSER_GID,
            "compiler_ld_preload_transport": (
                "private_unlinked_exact_snapshot_read_only_fd_via_proc_self_fd"
            ),
            "ld_preload_exact_single_entry": True,
            "arbitrary_LD_PRELOAD_override_allowed": False,
        },
        "candidate_launcher": {
            "absolute_path": ANDROID_LINKER64_PATH,
            "symlink_target": ANDROID_LINKER64_LINK_TARGET,
            "resolved_absolute_path": ANDROID_LINKER64_RESOLVED_PATH,
            "resolved_bytes": ANDROID_LINKER64_RESOLVED_BYTES,
            "resolved_sha256": ANDROID_LINKER64_RESOLVED_SHA256,
            "absolute_candidate_path_required": True,
            "candidate_runtime_ld_preload_allowed": False,
            "termux_wrapper_allowed": False,
        },
        "phone_system_runtime_files": [
            dict(item) for item in PHONE_SYSTEM_RUNTIME_FILES
        ],
        "runtime_mapping_identity": (
            "exact_path_device_inode_against_prevalidated_regular_file"
        ),
        "binary_publication": "renameat2_RENAME_NOREPLACE_same_directory",
    }


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def directory_tree_identity(root: Path) -> dict[str, Any]:
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or root.is_symlink():
        raise AdrenoGateError(f"toolchain tree root is unsafe: {root}")
    records: list[dict[str, Any]] = []
    regular_bytes = 0
    paths = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
    for path in paths:
        relative = path.relative_to(root).as_posix()
        entry = path.lstat()
        mode = f"{stat.S_IMODE(entry.st_mode):04o}"
        if stat.S_ISDIR(entry.st_mode):
            records.append(
                {"relative_path": relative, "type": "directory", "mode": mode}
            )
            continue
        if stat.S_ISLNK(entry.st_mode):
            records.append(
                {
                    "relative_path": relative,
                    "type": "symlink",
                    "mode": mode,
                    "target": os.readlink(path),
                }
            )
            continue
        if not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1:
            raise AdrenoGateError(f"toolchain tree entry is unsafe: {path}")
        payload = read_regular(path)
        regular_bytes += len(payload)
        records.append(
            {
                "relative_path": relative,
                "type": "regular",
                "mode": mode,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    return {
        "entry_count": len(records),
        "regular_bytes": regular_bytes,
        "root_sha256": sha256_bytes(canonical_json(records)),
    }


def _open_regular(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise AdrenoGateError(f"not a regular file: {path}")
    return descriptor


def read_regular(path: Path) -> bytes:
    descriptor = _open_regular(path)
    try:
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def sha256_path(path: Path) -> str:
    descriptor = _open_regular(path)
    digest = hashlib.sha256()
    try:
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def hash_range(path: Path, *, offset: int, length: int) -> str:
    if offset < 0 or length <= 0:
        raise AdrenoGateError("range offset and length must be positive")
    descriptor = _open_regular(path)
    digest = hashlib.sha256()
    remaining = length
    cursor = offset
    try:
        metadata = os.fstat(descriptor)
        if offset + length > metadata.st_size:
            raise AdrenoGateError(f"range exceeds file: {path}")
        while remaining:
            chunk = os.pread(descriptor, min(8 * 1024 * 1024, remaining), cursor)
            if not chunk:
                raise AdrenoGateError(f"short range read: {path}")
            digest.update(chunk)
            cursor += len(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def read_range(path: Path, *, offset: int, length: int) -> bytes:
    if offset < 0 or length <= 0:
        raise AdrenoGateError("range offset and length must be positive")
    descriptor = _open_regular(path)
    chunks: list[bytes] = []
    remaining = length
    cursor = offset
    try:
        metadata = os.fstat(descriptor)
        if offset + length > metadata.st_size:
            raise AdrenoGateError(f"range exceeds file: {path}")
        while remaining:
            chunk = os.pread(descriptor, min(8 * 1024 * 1024, remaining), cursor)
            if not chunk:
                raise AdrenoGateError(f"short range read: {path}")
            chunks.append(chunk)
            cursor += len(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def validate_regular(path: Path, *, expected_bytes: int, expected_sha256: str) -> None:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise AdrenoGateError(f"unsafe or non-regular file: {path}")
    if metadata.st_size != expected_bytes:
        raise AdrenoGateError(f"byte count mismatch: {path}")
    if sha256_path(path) != expected_sha256:
        raise AdrenoGateError(f"SHA-256 mismatch: {path}")


def strict_json_decode(payload: bytes, *, source: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise AdrenoGateError(f"non-finite JSON constant: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AdrenoGateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        result = json.loads(
            payload,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdrenoGateError(f"invalid JSON: {source}") from exc
    if not isinstance(result, dict):
        raise AdrenoGateError(f"JSON root must be an object: {source}")
    return result


def strict_json_load(path: Path) -> dict[str, Any]:
    return strict_json_decode(read_regular(path), source=str(path))


def write_exclusive(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short write: {path}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def resolve_relative(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise AdrenoGateError("relative path must be a nonempty string")
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise AdrenoGateError(f"unsafe relative path: {relative}")
    return root / value


def float32_to_bf16_rne_bits(value: float) -> int:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    exponent = bits & 0x7F800000
    mantissa = bits & 0x007FFFFF
    if exponent == 0x7F800000 and mantissa:
        return (bits >> 16) | 0x0040
    rounded = bits + 0x7FFF + ((bits >> 16) & 1)
    return (rounded >> 16) & 0xFFFF


def bf16_bits_to_float(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", (bits & 0xFFFF) << 16))[0]


def s16_input_to_bf16(payload: bytes) -> bytes:
    if len(payload) != INPUT_BYTES:
        raise AdrenoGateError("S16 source input byte count mismatch")
    result = bytearray(INPUT_BYTES)
    for index, (quantized,) in enumerate(struct.iter_unpack("<h", payload)):
        value = quantized * (1.0 / 512.0)
        struct.pack_into("<H", result, index * 2, float32_to_bf16_rne_bits(value))
    return bytes(result)


def off_s16_lattice_sentinel() -> bytes:
    """Build the frozen one-feature BF16 input that S16 factorization cannot encode."""

    result = bytearray(INPUT_BYTES)
    struct.pack_into("<H", result, 0, 0x3A80)
    if bf16_bits_to_float(0x3A80) != 2.0**-10:
        raise AdrenoGateError("sentinel BF16 value drift")
    if (bf16_bits_to_float(0x3A80) * 512.0).is_integer():
        raise AdrenoGateError("sentinel accidentally entered the S16 lattice")
    payload = bytes(result)
    if sha256_bytes(payload) != SENTINEL_INPUT_SHA256:
        raise AdrenoGateError("off-S16-lattice sentinel digest drift")
    return payload


def bf16_rne_scales(source_f32: bytes) -> tuple[bytes, bytes]:
    """Return exact-F32 BF16 values and compact BF16 bits.

    The exact-F32 form is checked against the preregistered S16-v2 transform
    digest.  The compact form is the only scale payload uploaded to the GPU.
    """

    if len(source_f32) != SCALE_F32_BYTES:
        raise AdrenoGateError("source scale byte count mismatch")
    exact_f32 = bytearray(SCALE_F32_BYTES)
    compact_bf16 = bytearray(SCALE_BF16_BYTES)
    for index, (value,) in enumerate(struct.iter_unpack("<f", source_f32)):
        if not math.isfinite(value) or value <= 0.0:
            raise AdrenoGateError(f"invalid row scale at index {index}")
        bf16_bits = float32_to_bf16_rne_bits(value)
        rounded = bf16_bits_to_float(bf16_bits)
        struct.pack_into("<f", exact_f32, index * 4, rounded)
        struct.pack_into("<H", compact_bf16, index * 2, bf16_bits)
    return bytes(exact_f32), bytes(compact_bf16)


def sentinel_reference_output(packed_weight: bytes, compact_scale_bf16: bytes) -> bytes:
    """Compute the exact full-width single-product reference for the 0x3a80 sentinel."""

    if len(packed_weight) != PACKED_WEIGHT_BYTES:
        raise AdrenoGateError("sentinel packed-weight byte count mismatch")
    if len(compact_scale_bf16) != SCALE_BF16_BYTES:
        raise AdrenoGateError("sentinel scale byte count mismatch")
    input_value = bf16_bits_to_float(0x3A80)
    result = bytearray(OUTPUT_BYTES)
    for row in range(OUTPUT_FEATURES):
        scale_bits = struct.unpack_from("<H", compact_scale_bf16, row * 2)[0]
        scale = bf16_bits_to_float(scale_bits)
        unsigned_code = packed_weight[row * PACKED_BYTES_PER_ROW] & 0x03
        weight_bits = float32_to_bf16_rne_bits((unsigned_code - 2) * scale)
        weight = bf16_bits_to_float(weight_bits)
        product_f32 = struct.unpack("<f", struct.pack("<f", input_value * weight))[0]
        struct.pack_into("<H", result, row * 2, float32_to_bf16_rne_bits(product_f32))
    return bytes(result)


def decode_bf16(
    payload: bytes, *, expected_count: int = OUTPUT_FEATURES
) -> list[float]:
    if len(payload) != expected_count * 2:
        raise AdrenoGateError("BF16 payload byte count mismatch")
    return [bf16_bits_to_float(bits) for (bits,) in struct.iter_unpack("<H", payload)]


def _top_k_indices(values: Sequence[float], k: int = 32) -> list[int]:
    if k <= 0 or k > len(values):
        raise AdrenoGateError("invalid top-k metric request")
    return sorted(range(len(values)), key=lambda index: (-values[index], index))[:k]


def vector_metrics(
    reference: Sequence[float], candidate: Sequence[float]
) -> dict[str, Any]:
    if len(reference) != len(candidate) or not reference:
        raise AdrenoGateError("metric vectors must have equal nonzero length")
    if any(not math.isfinite(value) for value in reference) or any(
        not math.isfinite(value) for value in candidate
    ):
        raise AdrenoGateError("non-finite projection output")
    errors = [right - left for left, right in zip(reference, candidate, strict=True)]
    squared_error = math.fsum(value * value for value in errors)
    squared_reference = math.fsum(value * value for value in reference)
    squared_candidate = math.fsum(value * value for value in candidate)
    dot = math.fsum(
        left * right for left, right in zip(reference, candidate, strict=True)
    )
    reference_top = _top_k_indices(reference)
    candidate_top = _top_k_indices(candidate)
    return {
        "max_abs": max(abs(value) for value in errors),
        "rms": math.sqrt(squared_error / len(errors)),
        "relative_l2": (
            math.sqrt(squared_error / squared_reference)
            if squared_reference
            else math.inf
        ),
        "cosine": (
            dot / math.sqrt(squared_reference * squared_candidate)
            if squared_reference and squared_candidate
            else 0.0
        ),
        "top_k_set_overlap": len(set(reference_top) & set(candidate_top)) / 32,
        "top_1_equal": reference_top[0] == candidate_top[0],
    }


def softmax_js_divergence(
    reference: Sequence[float], candidate: Sequence[float]
) -> float:
    if len(reference) != len(candidate) or not reference:
        raise AdrenoGateError("JSD vectors must have equal nonzero length")

    def probabilities(values: Sequence[float]) -> list[float]:
        maximum = max(values)
        exponentials = [math.exp(value - maximum) for value in values]
        denominator = math.fsum(exponentials)
        return [value / denominator for value in exponentials]

    left = probabilities(reference)
    right = probabilities(candidate)
    terms = []
    for left_value, right_value in zip(left, right, strict=True):
        midpoint = 0.5 * (left_value + right_value)
        term = 0.0
        if left_value:
            term += 0.5 * left_value * math.log(left_value / midpoint)
        if right_value:
            term += 0.5 * right_value * math.log(right_value / midpoint)
        terms.append(term)
    return math.fsum(terms)


def adjudicate_metrics(
    metrics: Mapping[str, Any], limits: Mapping[str, Any]
) -> tuple[bool, list[str]]:
    failures = []
    for metric in ("max_abs", "rms", "relative_l2"):
        if float(metrics[metric]) > float(limits[metric]):
            failures.append(f"{metric}_above_{limits[metric]}")
    if float(metrics["cosine"]) < float(limits["cosine_min"]):
        failures.append(f"cosine_below_{limits['cosine_min']}")
    if float(metrics["softmax_js_divergence"]) > float(
        limits["softmax_js_divergence_max"]
    ):
        failures.append(
            f"softmax_js_divergence_above_{limits['softmax_js_divergence_max']}"
        )
    if float(metrics["top_k_set_overlap"]) < float(limits["top_k_set_overlap_min"]):
        failures.append(f"top_k_set_overlap_below_{limits['top_k_set_overlap_min']}")
    if limits["top_1_equal"] and not metrics["top_1_equal"]:
        failures.append("top_1_changed")
    return not failures, failures


def frozen_thresholds() -> dict[str, Any]:
    return dict(FROZEN_THRESHOLDS)


def adjudicate_bf16_output(reference: bytes, candidate: bytes) -> dict[str, Any]:
    left = decode_bf16(reference)
    right = decode_bf16(candidate)
    metrics = vector_metrics(left, right)
    metrics["softmax_js_divergence"] = softmax_js_divergence(left, right)
    passed, failures = adjudicate_metrics(metrics, frozen_thresholds())
    return {"passed": passed, "failures": failures, "metrics": metrics}


def _extension_tokens(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        tokens = tuple(value.split())
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        tokens = tuple(value)
    else:
        raise AdrenoGateError("device_extensions must be a string or string list")
    if not tokens or len(tokens) != len(set(tokens)):
        raise AdrenoGateError("device extension list is empty or duplicated")
    return tokens


def normalize_opencl_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != OPENCL_CONTRACT_SCHEMA:
        raise AdrenoGateError("OpenCL contract schema mismatch")
    if payload.get("state") != "passed_scope":
        raise AdrenoGateError("OpenCL contract is not passed_scope")
    if payload.get("candidate_output_observed") is not False:
        raise AdrenoGateError("OpenCL contract contains candidate observations")
    if (
        payload.get("candidate_output_observation_scope")
        != "this_custody_run_only"
    ):
        raise AdrenoGateError("OpenCL candidate observation scope drifted")
    if payload.get("model_or_tensor_path_supplied") is not False:
        raise AdrenoGateError("OpenCL probe received model or tensor paths")
    if payload.get("model_or_tensor_access_count_measured") is not False:
        raise AdrenoGateError("OpenCL probe overclaimed an access trace")
    if (
        payload.get("model_or_tensor_access_observation")
        != "not_observed_no_paths_supplied"
    ):
        raise AdrenoGateError("OpenCL probe access observation drifted")
    expected_access_observation_basis = (
        "exclusive_probe_argv_and_source_bound_control_flow_no_syscall_trace"
    )
    if (
        payload.get("model_or_tensor_access_observation_basis")
        != expected_access_observation_basis
    ):
        raise AdrenoGateError("OpenCL probe access observation basis drifted")
    source_closure_sha256 = payload.get("source_closure_sha256")
    if not is_sha256(source_closure_sha256):
        raise AdrenoGateError("OpenCL contract source closure witness is invalid")
    custody_challenge = payload.get("custody_challenge")
    if not is_sha256(custody_challenge):
        raise AdrenoGateError("OpenCL custody challenge is invalid")
    expected_runtime_isolation = {
        "ld_preload_absent": True,
        "ld_library_path_absent": True,
        "termux_exec_mapping_absent": True,
    }
    if payload.get("runtime_isolation") != expected_runtime_isolation:
        raise AdrenoGateError("OpenCL probe runtime loader isolation drifted")
    if payload.get("runtime_mappings_observed") != list(REQUIRED_RUNTIME_MAPPINGS):
        raise AdrenoGateError("OpenCL probe runtime mappings drifted")
    expected_runtime_mapping_identity = (
        "exact_path_device_inode_against_prevalidated_regular_file"
    )
    if payload.get("runtime_mapping_identity") != expected_runtime_mapping_identity:
        raise AdrenoGateError("OpenCL runtime mapping identity method drifted")
    loader = payload.get("loader")
    identity = payload.get("identity")
    limits = payload.get("limits")
    compiler = payload.get("compiler_probe")
    if not all(
        isinstance(value, dict) for value in (loader, identity, limits, compiler)
    ):
        raise AdrenoGateError("OpenCL contract sections are incomplete")
    assert isinstance(loader, dict)
    assert isinstance(identity, dict)
    assert isinstance(limits, dict)
    assert isinstance(compiler, dict)
    required_strings = (
        "platform_name",
        "platform_vendor",
        "platform_version",
        "device_name",
        "device_vendor",
        "driver_version",
        "device_version",
        "opencl_c_version",
    )
    for field in required_strings:
        if not isinstance(identity.get(field), str) or not identity[field]:
            raise AdrenoGateError(f"OpenCL identity field missing: {field}")
    expected_identity = {
        "platform_name": "QUALCOMM Snapdragon(TM)",
        "platform_vendor": "QUALCOMM",
        "platform_version": "OpenCL 3.0 QUALCOMM build: 0800.40",
        "device_name": "QUALCOMM Adreno(TM) 830",
        "device_vendor": "QUALCOMM",
        "driver_version": ("OpenCL 3.0 QUALCOMM build: 0800.40 Compiler E031.47.18.30"),
        "device_version": "OpenCL 3.0 Adreno(TM) 830",
        "opencl_c_version": "OpenCL C 3.0 Adreno(TM) 830",
    }
    if any(identity.get(key) != value for key, value in expected_identity.items()):
        raise AdrenoGateError("OpenCL device identity drifted")
    extension_string = identity.get("device_extensions")
    if (
        not isinstance(extension_string, str)
        or len(extension_string.encode("utf-8")) != OPENCL_DEVICE_EXTENSIONS_BYTES
        or sha256_bytes(extension_string.encode("utf-8"))
        != OPENCL_DEVICE_EXTENSIONS_SHA256
    ):
        raise AdrenoGateError("OpenCL device extensions set drifted")
    extensions = _extension_tokens(extension_string)
    missing = [item for item in REQUIRED_DEVICE_EXTENSIONS if item not in extensions]
    if missing:
        raise AdrenoGateError(f"required OpenCL extensions absent: {missing}")
    max_group = limits.get("max_work_group_size")
    production_max_group = limits.get("production_kernel_max_work_group_size")
    local_mem = limits.get("local_mem_bytes")
    max_alloc = limits.get("max_mem_alloc_bytes")
    if isinstance(max_group, bool) or not isinstance(max_group, int) or max_group != 1_024:
        raise AdrenoGateError("OpenCL maximum workgroup size drifted")
    if (
        not isinstance(production_max_group, int)
        or isinstance(production_max_group, bool)
        or production_max_group < LOCAL_SIZE
        or production_max_group > max_group
    ):
        raise AdrenoGateError("production kernel did not admit local size 64")
    if (
        isinstance(local_mem, bool)
        or not isinstance(local_mem, int)
        or local_mem != 32_768
    ):
        raise AdrenoGateError("OpenCL local memory size drifted")
    if (
        isinstance(max_alloc, bool)
        or not isinstance(max_alloc, int)
        or max_alloc != 1_073_741_824
    ):
        raise AdrenoGateError("OpenCL maximum allocation size drifted")
    if identity.get("endian_little") is not True or identity.get("address_bits") != 64:
        raise AdrenoGateError(
            "OpenCL device ABI is not the frozen little-endian 64-bit ABI"
        )
    loaded_path = loader.get("loaded_path")
    route = loader.get("route")
    if not isinstance(loaded_path, str) or not loaded_path:
        raise AdrenoGateError("OpenCL loader path is missing")
    if route != "android_sphal" or loaded_path != "/vendor/lib64/libOpenCL.so":
        raise AdrenoGateError("OpenCL loader is not the frozen Android SPHAL route")
    expected_compiler = {
        "build_options": "-cl-std=CL3.0",
        "build_succeeded": True,
        "production_kernel_compiled": True,
        "local_size_64_admitted": True,
        "bf16_product_succeeded": True,
        "bf16_intrinsic_signature": ("float_qcom_mad32_bf16_ushort_ushort_float"),
        "intrinsic_and_rne_runtime_conformance": True,
        "production_buffer_allocation_succeeded": True,
        "production_buffer_bytes": [
            PACKED_WEIGHT_BYTES,
            SCALE_BF16_BYTES,
            INPUT_BYTES,
            OUTPUT_BYTES,
        ],
        "production_kernel_arguments_bound": True,
        "fast_math_enabled": False,
        "subgroup_reduce_used": False,
    }
    if compiler.get("build_options") != expected_compiler["build_options"]:
        raise AdrenoGateError("OpenCL language standard drifted")
    if compiler.get("fast_math_enabled") is not False:
        raise AdrenoGateError("OpenCL fast math is forbidden")
    if compiler != expected_compiler:
        raise AdrenoGateError("OpenCL compiler and arithmetic probe drifted")
    arithmetic_bits = payload.get("arithmetic_observed_bits")
    if arithmetic_bits != [
        "0x40a00000",
        "0xbfc00000",
        "0x40800000",
        "0x3f820200",
        "0x00003f80",
        "0x00003f82",
    ]:
        raise AdrenoGateError("OpenCL arithmetic observed bits drifted")
    return {
        "schema_version": OPENCL_CONTRACT_SCHEMA,
        "state": "passed_scope",
        "candidate_output_observed": False,
        "candidate_output_observation_scope": "this_custody_run_only",
        "model_or_tensor_path_supplied": False,
        "model_or_tensor_access_count_measured": False,
        "model_or_tensor_access_observation": "not_observed_no_paths_supplied",
        "model_or_tensor_access_observation_basis": (
            expected_access_observation_basis
        ),
        "source_closure_sha256": source_closure_sha256,
        "custody_challenge": custody_challenge,
        "runtime_isolation": expected_runtime_isolation,
        "runtime_mappings_observed": list(REQUIRED_RUNTIME_MAPPINGS),
        "runtime_mapping_identity": expected_runtime_mapping_identity,
        "loader": {"loaded_path": loaded_path, "route": route},
        "identity": {
            **{field: identity[field] for field in required_strings},
            "device_extensions": extension_string,
            "address_bits": 64,
            "endian_little": True,
        },
        "limits": {
            "max_work_group_size": max_group,
            "production_kernel_max_work_group_size": production_max_group,
            "local_mem_bytes": local_mem,
            "max_mem_alloc_bytes": max_alloc,
        },
        "compiler_probe": expected_compiler,
        "arithmetic_observed_bits": list(arithmetic_bits),
    }


def _validate_s16_falsification(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != S16_FALSIFICATION_SCHEMA:
        raise AdrenoGateError("S16 falsification schema mismatch")
    if payload.get("status") != "falsified_scope":
        raise AdrenoGateError("S16 predecessor is not falsified_scope")
    if payload.get("candidate_id") != S16_CANDIDATE_ID:
        raise AdrenoGateError("unexpected S16 predecessor candidate")
    adjudication = payload.get("adjudication")
    transition = payload.get("branch_transition")
    if not isinstance(adjudication, dict) or not isinstance(transition, dict):
        raise AdrenoGateError("S16 falsification decision is incomplete")
    if adjudication.get("standard_htp_s16_family_exhausted") is not True:
        raise AdrenoGateError("S16 family is not exhaustively falsified")
    if transition.get("mandatory_successor") != (
        "Adreno_OpenCL_direct_packed_INT2_BF16_product_FP32_accumulation_BF16_RNE_output"
    ):
        raise AdrenoGateError("OpenCL candidate is not the mandatory successor")
    bindings = payload.get("governing_bindings")
    if not isinstance(bindings, dict) or bindings.get("oracle_gate_sha256") != (
        S16_ORACLE_GATE_SHA256
    ):
        raise AdrenoGateError("S16 oracle gate binding drifted")


def _validate_frontier_selector(selector: Mapping[str, Any]) -> None:
    selected = selector.get("immutable_candidate_contract")
    sentinel = selector.get("off_lattice_sentinel_contract")
    authority = selector.get("frozen_authority_gate")
    if not all(isinstance(value, dict) for value in (selected, sentinel, authority)):
        raise AdrenoGateError("frontier selector contracts are incomplete")
    assert isinstance(selected, dict)
    assert isinstance(sentinel, dict)
    assert isinstance(authority, dict)
    expected_selected = {
        "candidate_id": CANDIDATE_ID,
        "model_sha256": MODEL_SHA256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "packed_weight_bytes": PACKED_WEIGHT_BYTES,
        "original_scale_sha256": SCALE_F32_SHA256,
        "original_scale_bytes": SCALE_F32_BYTES,
        "scale_transform": (
            "float32_to_bfloat16_RNE_then_signed_INT2_product_to_bfloat16_RNE"
        ),
        "input_dtype": "bfloat16_bits_in_ushort",
        "input_shape": [1, 1, INPUT_FEATURES],
        "weight_storage": "direct_U2_four_lanes_per_byte_no_dense_expansion",
        "signed_lane_mapping": [-2, -1, 0, 1],
        "output_dtype": "bfloat16_bits_in_ushort",
        "output_shape": [1, 1, OUTPUT_FEATURES],
        "product_intrinsic": "qcom_mad32_bf16_scalar_ushort_ushort_float",
        "accumulator_dtype": "float32",
        "workgroup_size": LOCAL_SIZE,
        "rows_per_workgroup": ROWS_PER_WORKGROUP,
        "workgroup_count": WORKGROUP_COUNT,
        "packed_byte_lane_mapping": "lane_l_consumes_byte_l_plus_64t_for_t_0_through_9",
        "lane_accumulators": 4,
        "lane_accumulator_combine": "(a0_plus_a1)_plus_(a2_plus_a3)",
        "workgroup_reduction": "fixed_local_memory_strides_32_16_8_4_2_1",
        "subgroup_reduce_builtin_used": False,
        "output_rounding": "bit_exact_bfloat16_round_to_nearest_even",
        "weight_residency": "one_upload_one_context_all_cases_and_replays",
        "full_case_replays": 2,
        "byte_identical_replay_required": True,
        "dense_weight_expansion_allowed": False,
        "numeric_ranking_threshold_subset_sha256": sha256_bytes(
            canonical_json(FROZEN_THRESHOLDS)
        ),
        "thresholds_changed": False,
        "candidate_output_observed": False,
    }
    for key, expected in expected_selected.items():
        if selected.get(key) != expected:
            raise AdrenoGateError(f"frontier selector candidate field drifted: {key}")
    expected_sentinel = {
        "input_shape": [1, 1, INPUT_FEATURES],
        "construction": "all_zero_BF16_except_one_preregistered_feature_equal_to_2^-10_BF16",
        "nonzero_feature_index": 0,
        "nonzero_value_bfloat16_bits": "0x3a80",
        "value_is_multiple_of_2^-9": False,
        "input_bytes": INPUT_BYTES,
        "input_sha256": SENTINEL_INPUT_SHA256,
        "reference_output_bytes": OUTPUT_BYTES,
        "reference_rule": "single_product_exact_BF16_semantics_without_reduction_order_ambiguity",
        "pass_rule": (
            "full_width_524288_byte_reference_candidate_equality_and_byte_identical_replays"
        ),
        "candidate_output_observed": False,
    }
    for key, expected in expected_sentinel.items():
        if sentinel.get(key) != expected:
            raise AdrenoGateError(f"frontier selector sentinel field drifted: {key}")
    expected_authority = {
        "case_ids": [case["case_id"] for case in FROZEN_CASES],
        "authority_output_sha256": [case["authority_sha256"] for case in FROZEN_CASES],
        **FROZEN_THRESHOLDS,
        "every_metric_every_case_must_pass": True,
        "replay_outputs_must_be_byte_identical": True,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            raise AdrenoGateError(f"frontier selector authority field drifted: {key}")


def _validate_opencl_evidence(
    report: Mapping[str, Any], selector: Mapping[str, Any], report_sha256: str
) -> dict[str, Any]:
    if report.get("schema_version") != "gemma4_e4b_adreno_opencl_contract_report_v1":
        raise AdrenoGateError("OpenCL evidence report schema mismatch")
    if report.get("status") != "passed_scope":
        raise AdrenoGateError("OpenCL evidence report is not passed_scope")
    custody = report.get("custody")
    identity = report.get("device_identity")
    loader = report.get("loader_contract")
    extension = report.get("extension_contract")
    product = report.get("bfloat16_product_contract")
    arithmetic = report.get("arithmetic_conformance")
    workgroup = report.get("workgroup_contract")
    if not all(
        isinstance(value, dict)
        for value in (
            custody,
            identity,
            loader,
            extension,
            product,
            arithmetic,
            workgroup,
        )
    ):
        raise AdrenoGateError("OpenCL evidence report is incomplete")
    if custody.get("model_or_tensor_access_count") != 0:
        raise AdrenoGateError("OpenCL evidence report accessed model tensors")
    if identity.get("android_build_fingerprint_sha256") != (
        ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
    ):
        raise AdrenoGateError("Android build fingerprint evidence drifted")
    loader_roles = {
        "opencl_icd": "opencl_icd",
        "adreno_opencl_driver": "adreno_opencl_driver",
        "adreno_opencl_compiler": "adreno_opencl_compiler",
        "adreno_utils": "adreno_utils",
    }
    for frozen in VENDOR_RUNTIME_FILES:
        observed = loader.get(loader_roles[str(frozen["role"])])
        if not isinstance(observed, dict):
            raise AdrenoGateError("OpenCL vendor runtime evidence is incomplete")
        if (
            observed.get("bytes") != frozen["bytes"]
            or observed.get("sha256") != frozen["sha256"]
        ):
            raise AdrenoGateError("OpenCL vendor runtime evidence drifted")
    if extension.get("required_extensions_present") != [
        "cl_qcom_bfloat16_product",
        "cl_khr_subgroups",
    ]:
        raise AdrenoGateError("OpenCL required extension evidence drifted")
    if product.get("required_build_option") != "-cl-std=CL3.0":
        raise AdrenoGateError("OpenCL build-option evidence drifted")
    if product.get("exact_signature") != "float_qcom_mad32_bf16_ushort_ushort_float":
        raise AdrenoGateError("OpenCL BF16 ABI evidence drifted")
    if arithmetic.get("bf16_3f81_times_bf16_3f81_f32_bits") != "0x3f820200":
        raise AdrenoGateError("OpenCL BF16 arithmetic evidence drifted")
    if (
        arithmetic.get("bfloat16_rne_tie_3f808000") != "0x3f80"
        or arithmetic.get("bfloat16_rne_tie_3f818000") != "0x3f82"
    ):
        raise AdrenoGateError("OpenCL BF16 RNE evidence drifted")
    if workgroup.get("selected_local_workgroup_size") != LOCAL_SIZE:
        raise AdrenoGateError("OpenCL workgroup evidence drifted")
    if workgroup.get("required_reduction") != "explicit_fixed_local_memory_binary_tree":
        raise AdrenoGateError("OpenCL reduction evidence drifted")
    selector_contract = selector.get("live_opencl_contract")
    if not isinstance(selector_contract, dict):
        raise AdrenoGateError("frontier selector lacks live OpenCL contract")
    if selector_contract.get("report_sha256") != report_sha256:
        raise AdrenoGateError("frontier selector OpenCL report binding mismatch")
    if selector_contract.get("opencl_icd_sha256") != VENDOR_RUNTIME_FILES[0]["sha256"]:
        raise AdrenoGateError("frontier selector ICD binding drifted")
    if (
        selector_contract.get("adreno_opencl_driver_sha256")
        != VENDOR_RUNTIME_FILES[1]["sha256"]
    ):
        raise AdrenoGateError("frontier selector driver binding drifted")
    if (
        selector_contract.get("adreno_opencl_compiler_sha256")
        != VENDOR_RUNTIME_FILES[2]["sha256"]
    ):
        raise AdrenoGateError("frontier selector compiler binding drifted")
    return {
        "report_sha256": report_sha256,
        "android_build_fingerprint_stdout_sha256": (
            ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": [dict(item) for item in VENDOR_RUNTIME_FILES],
    }


def _git_output(root: Path, *arguments: str) -> str:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AdrenoGateError("git source binding failed") from exc
    value = process.stdout.strip()
    if not value:
        raise AdrenoGateError("git source binding returned empty output")
    return value


def _git_tree_entry(root: Path, revision: str, relative: str) -> tuple[str, str]:
    fields = _git_output(root, "ls-tree", revision, "--", relative).split(maxsplit=3)
    if len(fields) != 4:
        raise AdrenoGateError(f"git tree entry is invalid: {relative}")
    mode, kind, object_id, observed_relative = fields
    if (
        mode not in {"100644", "100755"}
        or kind != "blob"
        or observed_relative != relative
    ):
        raise AdrenoGateError(f"git tree entry drifted: {relative}")
    return mode, object_id


def _working_git_mode(path: Path) -> str:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise AdrenoGateError(f"source closure path is not regular: {path}")
    return "100755" if metadata.st_mode & 0o111 else "100644"


def source_closure(root: Path) -> tuple[str, list[dict[str, Any]]]:
    revision = _git_output(root, "rev-parse", "HEAD")
    records = []
    for relative in SOURCE_CLOSURE:
        path = resolve_relative(root, relative)
        payload = read_regular(path)
        head_blob = _git_output(root, "rev-parse", f"HEAD:{relative}")
        head_mode, tree_blob = _git_tree_entry(root, revision, relative)
        working_blob = _git_output(root, "hash-object", "--", relative)
        working_mode = _working_git_mode(path)
        if working_blob != head_blob or tree_blob != head_blob:
            raise AdrenoGateError(f"source blob is not committed at HEAD: {relative}")
        if working_mode != head_mode:
            raise AdrenoGateError(f"source mode is not committed at HEAD: {relative}")
        if relative in SOURCE_EXECUTABLES and (
            head_mode != "100755" or not os.access(path, os.X_OK)
        ):
            raise AdrenoGateError(f"required source is not executable: {relative}")
        records.append(
            {
                "relative_path": relative,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_blob_oid": head_blob,
                "git_mode": head_mode,
            }
        )
    return revision, records


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_noreplace(source: Path, destination: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    renameat2 = getattr(library, "renameat2", None)
    linux_or_android = sys.platform.startswith("linux") or sys.platform == "android"
    if linux_or_android and renameat2 is not None:
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(-100, source_bytes, -100, destination_bytes, 1)
    elif linux_or_android:
        syscall_numbers = {
            "aarch64": 276,
            "arm64": 276,
            "riscv64": 276,
            "x86_64": 316,
            "amd64": 316,
            "armv7l": 382,
            "i386": 353,
            "i686": 353,
        }
        number = syscall_numbers.get(platform.machine().casefold())
        syscall = getattr(library, "syscall", None)
        if number is None or syscall is None:
            raise AdrenoGateError("atomic no-replace rename is unavailable")
        syscall.restype = ctypes.c_long
        result = syscall(number, -100, source_bytes, -100, destination_bytes, 1)
    elif sys.platform == "darwin":
        renamex_np = getattr(library, "renamex_np", None)
        if renamex_np is None:
            raise AdrenoGateError("atomic no-replace rename is unavailable")
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source_bytes, destination_bytes, 0x00000004)
    else:
        raise AdrenoGateError("atomic no-replace rename is unsupported")
    if result == 0:
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(destination)
    raise OSError(error, os.strerror(error), destination)


def _publish_preregistration_directory(
    output_dir: Path, preregistration: Mapping[str, Any]
) -> None:
    parent = output_dir.parent
    parent_metadata = parent.lstat()
    if not stat.S_ISDIR(parent_metadata.st_mode) or parent.is_symlink():
        raise AdrenoGateError("preregistration parent must be a real directory")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=parent))
    os.chmod(temporary, 0o700)
    try:
        encoded = canonical_json(preregistration)
        prereg_path = temporary / "preregistration.json"
        write_exclusive(prereg_path, encoded)
        digest = sha256_bytes(encoded)
        write_exclusive(
            prereg_path.with_suffix(".json.sha256"),
            f"{digest}  {prereg_path.name}\n".encode("ascii"),
        )
        _fsync_directory(temporary)
        _rename_noreplace(temporary, output_dir)
        _fsync_directory(parent)
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        raise


def _case_contracts() -> list[dict[str, Any]]:
    records = []
    for case in FROZEN_CASES:
        case_id = case["case_id"]
        records.append(
            {
                **case,
                "s16_source_bytes": INPUT_BYTES,
                "bf16_input_bytes": INPUT_BYTES,
                "bf16_input_relative_path": f"private_inputs/{case_id}.bf16.raw",
                "authority_bytes": OUTPUT_BYTES,
                "output_bytes": OUTPUT_BYTES,
                "replay_output_relative_paths": [
                    f"private_outputs/{case_id}.replay0.bf16.raw",
                    f"private_outputs/{case_id}.replay1.bf16.raw",
                ],
                "candidate_output_present": False,
            }
        )
    return records


def _validate_preflight_build_record(record: object) -> tuple[int, str, str, str]:
    expected_keys = {
        "binary_bytes",
        "binary_sha256",
        "toolchain_version_sha256",
        "toolchain_resolved_sha256",
        "linker_version_sha256",
        "linker_resolved_sha256",
        "cxx_runtime_sha256",
        "compiler_arguments",
        "source_closure_sha256",
        "native_source_snapshot_sha256",
        "termux_exec_interposer_sha256",
        "termux_exec_transport",
        "binary_publication",
        "build_elapsed_ns",
        "stdout_sha256",
        "stderr_sha256",
    }
    if not isinstance(record, dict) or set(record) != expected_keys:
        raise AdrenoGateError("source-neutral build record shape drifted")
    binary_bytes = record.get("binary_bytes")
    binary_sha256 = record.get("binary_sha256")
    expected_values = {
        "toolchain_version_sha256": TERMUX_CLANGXX_VERSION_STDOUT_SHA256,
        "toolchain_resolved_sha256": TERMUX_CLANGXX_RESOLVED_SHA256,
        "linker_version_sha256": TERMUX_LLD_VERSION_STDOUT_SHA256,
        "linker_resolved_sha256": TERMUX_LLD_RESOLVED_SHA256,
        "cxx_runtime_sha256": TERMUX_LIBCXX_SHA256,
        "compiler_arguments": list(NATIVE_BUILD_ARGUMENTS),
        "termux_exec_interposer_sha256": TERMUX_EXEC_INTERPOSER_SHA256,
        "termux_exec_transport": (
            "private_unlinked_exact_snapshot_read_only_fd_via_proc_self_fd"
        ),
        "binary_publication": "renameat2_RENAME_NOREPLACE_same_directory",
    }
    if any(record.get(key) != value for key, value in expected_values.items()):
        raise AdrenoGateError("source-neutral build identity drifted")
    if (
        isinstance(binary_bytes, bool)
        or not isinstance(binary_bytes, int)
        or binary_bytes <= 0
        or not is_sha256(binary_sha256)
        or isinstance(record.get("build_elapsed_ns"), bool)
        or not isinstance(record.get("build_elapsed_ns"), int)
        or record["build_elapsed_ns"] < 0
        or not is_sha256(record.get("stdout_sha256"))
        or not is_sha256(record.get("stderr_sha256"))
        or not is_sha256(record.get("source_closure_sha256"))
        or not is_sha256(record.get("native_source_snapshot_sha256"))
        or record.get("stdout_sha256") != sha256_bytes(b"")
        or record.get("stderr_sha256") != sha256_bytes(b"")
    ):
        raise AdrenoGateError("source-neutral build observation is invalid")
    assert isinstance(binary_sha256, str)
    return (
        binary_bytes,
        binary_sha256,
        str(record["source_closure_sha256"]),
        str(record["native_source_snapshot_sha256"]),
    )


def _validate_source_neutral_preflight(
    payload: object,
    *,
    source_revision: str,
    closure: list[dict[str, Any]],
    opencl_raw: bytes,
    opencl: Mapping[str, Any],
) -> tuple[int, str]:
    expected_keys = {
        "schema_version",
        "state",
        "candidate_output_observed",
        "candidate_output_observation_scope",
        "model_or_tensor_path_supplied",
        "model_or_tensor_access_count_measured",
        "model_or_tensor_access_observation",
        "model_or_tensor_access_observation_basis",
        "source_revision",
        "custody_challenge",
        "source_closure",
        "source_closure_sha256",
        "source_checkout_clean_before_and_after",
        "build",
        "probe",
        "platform_identity",
        "custody",
        "nonclaims",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise AdrenoGateError("source-neutral preflight report shape drifted")
    expected_source_closure_sha256 = sha256_bytes(canonical_json(closure))
    if (
        payload.get("schema_version") != SOURCE_NEUTRAL_PREFLIGHT_SCHEMA
        or payload.get("state") != "passed_scope"
        or payload.get("candidate_output_observed") is not False
        or payload.get("candidate_output_observation_scope")
        != "this_custody_run_only"
        or payload.get("model_or_tensor_path_supplied") is not False
        or payload.get("model_or_tensor_access_count_measured") is not False
        or payload.get("model_or_tensor_access_observation")
        != "not_observed_no_paths_supplied"
        or payload.get("model_or_tensor_access_observation_basis")
        != "exclusive_probe_argv_and_source_bound_control_flow_no_syscall_trace"
        or payload.get("source_revision") != source_revision
        or not is_sha256(payload.get("custody_challenge"))
        or payload.get("source_closure") != closure
        or payload.get("source_closure_sha256") != expected_source_closure_sha256
        or payload.get("source_checkout_clean_before_and_after") is not True
    ):
        raise AdrenoGateError("source-neutral preflight source binding drifted")
    build = payload.get("build")
    if (
        not isinstance(build, dict)
        or set(build) != {"first", "second", "byte_identical_rebuild"}
        or build.get("byte_identical_rebuild") is not True
    ):
        raise AdrenoGateError("source-neutral preflight rebuild proof drifted")
    first_identity = _validate_preflight_build_record(build.get("first"))
    second_identity = _validate_preflight_build_record(build.get("second"))
    if first_identity != second_identity:
        raise AdrenoGateError("source-neutral preflight binaries differ")
    if first_identity[2] != expected_source_closure_sha256:
        raise AdrenoGateError("source-neutral binary source witness drifted")
    closure_by_path = {record["relative_path"]: record for record in closure}
    expected_snapshot = [
        {
            "relative_path": relative,
            "snapshot_name": Path(relative).name,
            "bytes": closure_by_path[relative]["bytes"],
            "sha256": closure_by_path[relative]["sha256"],
        }
        for relative in NATIVE_BUILD_SOURCE_FILES
    ]
    if first_identity[3] != sha256_bytes(canonical_json(expected_snapshot)):
        raise AdrenoGateError("source-neutral native source snapshot drifted")
    probe = payload.get("probe")
    expected_probe_keys = {
        "return_code",
        "elapsed_ns",
        "stdout_sha256",
        "stderr_sha256",
        "launched_binary_bytes",
        "launched_binary_sha256",
        "process_receipt",
        "contract_bytes",
        "contract_sha256",
        "contract_canonical_sha256",
        "runtime_isolation",
        "runtime_mapping_identity",
        "binary_snapshot_unlinked_before_launch",
        "launcher",
        "child_environment_keys",
        "loader_injection_environment_absent",
    }
    empty_sha256 = sha256_bytes(b"")
    process_receipt = probe.get("process_receipt") if isinstance(probe, dict) else None
    valid_process_receipt = (
        isinstance(process_receipt, dict)
        and set(process_receipt)
        == {
            "pid",
            "pidfd_opened",
            "pidfd_inode",
            "pidfd_poll_ready",
            "timeout_seconds",
            "waitid_pid",
            "waitid_code",
            "waitid_status",
            "popen_return_code",
        }
        and isinstance(process_receipt.get("pid"), int)
        and not isinstance(process_receipt.get("pid"), bool)
        and process_receipt["pid"] > 0
        and process_receipt.get("pidfd_opened") is True
        and isinstance(process_receipt.get("pidfd_inode"), int)
        and not isinstance(process_receipt.get("pidfd_inode"), bool)
        and process_receipt["pidfd_inode"] > 0
        and process_receipt.get("pidfd_poll_ready") is True
        and process_receipt.get("timeout_seconds") == 600
        and process_receipt.get("waitid_pid") == process_receipt.get("pid")
        and process_receipt.get("waitid_code") == os.CLD_EXITED
        and process_receipt.get("waitid_status") == 0
        and process_receipt.get("popen_return_code") == 0
    )
    if (
        not isinstance(probe, dict)
        or set(probe) != expected_probe_keys
        or isinstance(probe.get("return_code"), bool)
        or not isinstance(probe.get("return_code"), int)
        or probe.get("return_code") != 0
        or isinstance(probe.get("elapsed_ns"), bool)
        or not isinstance(probe.get("elapsed_ns"), int)
        or probe["elapsed_ns"] < 0
        or probe.get("stdout_sha256") != empty_sha256
        or probe.get("stderr_sha256") != empty_sha256
        or probe.get("launched_binary_bytes") != first_identity[0]
        or probe.get("launched_binary_sha256") != first_identity[1]
        or not valid_process_receipt
        or probe.get("contract_bytes") != len(opencl_raw)
        or probe.get("contract_sha256") != sha256_bytes(opencl_raw)
        or probe.get("contract_canonical_sha256")
        != sha256_bytes(canonical_json(opencl))
        or opencl.get("source_closure_sha256") != expected_source_closure_sha256
        or opencl.get("custody_challenge") != payload.get("custody_challenge")
        or probe.get("runtime_isolation") != opencl.get("runtime_isolation")
        or probe.get("runtime_mapping_identity")
        != "exact_path_device_inode_against_prevalidated_regular_file"
        or probe.get("runtime_mapping_identity")
        != opencl.get("runtime_mapping_identity")
        or probe.get("binary_snapshot_unlinked_before_launch") is not True
        or probe.get("launcher") != ANDROID_LINKER64_PATH
        or probe.get("child_environment_keys")
        != ["HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "TZ"]
        or probe.get("loader_injection_environment_absent") is not True
    ):
        raise AdrenoGateError("source-neutral OpenCL probe binding drifted")
    expected_platform = {
        "android_build_fingerprint_stdout_sha256": (
            ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": [dict(item) for item in VENDOR_RUNTIME_FILES],
        "android_linker64_sha256": ANDROID_LINKER64_RESOLVED_SHA256,
        "compiler_sha256": TERMUX_CLANGXX_RESOLVED_SHA256,
        "linker_sha256": TERMUX_LLD_RESOLVED_SHA256,
        "cxx_runtime_sha256": TERMUX_LIBCXX_SHA256,
        "termux_exec_source_sha256": TERMUX_EXEC_INTERPOSER_SHA256,
        "python_runtime_files": [dict(item) for item in TERMUX_PYTHON_RUNTIME_FILES],
        "python_stdlib_tree": {
            "absolute_path": TERMUX_PYTHON_STDLIB_DIR,
            **TERMUX_PYTHON_STDLIB_TREE_IDENTITY,
        },
        "compiler_runtime_libraries": [
            dict(item) for item in TERMUX_COMPILER_RUNTIME_FILES
        ],
        "compiler_resource_tree": {
            "absolute_path": TERMUX_CLANG_RESOURCE_DIR,
            **TERMUX_CLANG_RESOURCE_TREE_IDENTITY,
        },
        "include_tree": {
            "absolute_path": TERMUX_INCLUDE_DIR,
            **TERMUX_INCLUDE_TREE_IDENTITY,
        },
        "link_input_files": [dict(item) for item in TERMUX_LINK_INPUT_FILES],
        "phone_system_runtime_files": [
            dict(item) for item in PHONE_SYSTEM_RUNTIME_FILES
        ],
    }
    expected_custody = {
        "source_neutral_build_directory": True,
        "fresh_host_challenge_bound": True,
        "authorized_adb_forwarded_ssh_custody_receipt_required_for_admission": True,
        "model_tensor_input_reference_or_candidate_payload_path_supplied": False,
        "sanitized_hash_bound_metadata_egress_allowed": True,
    }
    expected_nonclaims = [
        "no_candidate_logits_observed",
        "no_authority_metric_result",
        "no_model_or_tensor_execution",
        "no_performance_claim",
        "no_kernel_level_filesystem_access_trace",
        "no_hardware_attestation",
        "no_resistance_to_malicious_same_uid_or_fully_compromised_phone",
    ]
    if (
        payload.get("platform_identity") != expected_platform
        or payload.get("custody") != expected_custody
        or payload.get("nonclaims") != expected_nonclaims
    ):
        raise AdrenoGateError("source-neutral preflight custody or platform drifted")
    return first_identity[0], first_identity[1]


def _validate_source_neutral_preflight_transaction(
    report_path: Path, report_raw: bytes, report: Mapping[str, Any]
) -> str:
    parent = report_path.parent
    completion_path = parent / "PREFLIGHT_COMPLETE.json"
    report_metadata = report_path.lstat()
    completion_metadata = completion_path.lstat() if completion_path.exists() else None
    if (
        report_path.name != "preflight_report.json"
        or not stat.S_ISREG(report_metadata.st_mode)
        or report_metadata.st_nlink != 1
        or not parent.is_dir()
        or parent.is_symlink()
        or completion_metadata is None
        or not stat.S_ISREG(completion_metadata.st_mode)
        or completion_metadata.st_nlink != 1
        or completion_path.is_symlink()
        or (parent / "PREFLIGHT_BLOCKER.json").exists()
        or (parent / "PREFLIGHT_BLOCKER.json").is_symlink()
    ):
        raise AdrenoGateError("source-neutral preflight transaction is unsafe")
    report_sha256 = sha256_bytes(report_raw)
    expected_sidecar = f"{report_sha256}  preflight_report.json\n".encode("ascii")
    sidecar_path = parent / "preflight_report.json.sha256"
    validate_regular(
        sidecar_path,
        expected_bytes=len(expected_sidecar),
        expected_sha256=sha256_bytes(expected_sidecar),
    )
    if read_regular(sidecar_path) != expected_sidecar:
        raise AdrenoGateError("source-neutral preflight sidecar drifted")
    completion_raw = read_regular(completion_path)
    completion = strict_json_decode(completion_raw, source=str(completion_path))
    build = report.get("build")
    probe = report.get("probe")
    expected_completion = {
        "schema_version": SOURCE_NEUTRAL_PREFLIGHT_COMPLETION_SCHEMA,
        "state": "complete",
        "report_sha256": report_sha256,
        "source_revision": report.get("source_revision"),
        "binary_sha256": (
            build.get("first", {}).get("binary_sha256")
            if isinstance(build, dict)
            else None
        ),
        "contract_sha256": (
            probe.get("contract_sha256") if isinstance(probe, dict) else None
        ),
        "custody_challenge": report.get("custody_challenge"),
    }
    if completion != expected_completion:
        raise AdrenoGateError("source-neutral preflight completion drifted")
    return sha256_bytes(completion_raw)


def _is_microsecond_utc(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 27
        and value[4] == "-"
        and value[7] == "-"
        and value[10] == "T"
        and value[13] == ":"
        and value[16] == ":"
        and value[19] == "."
        and value.endswith("Z")
        and all(character.isdigit() for character in value if character not in "-T:.Z")
    )


def _is_lower_uuid(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    if any(value[index] != "-" for index in (8, 13, 18, 23)):
        return False
    return all(
        character in "0123456789abcdef"
        for index, character in enumerate(value)
        if index not in {8, 13, 18, 23}
    )


def _validate_adb_custody_receipt_transaction(
    receipt_path: Path,
    *,
    preflight_report_path: Path,
    preflight_report_raw: bytes,
    preflight_report: Mapping[str, Any],
    opencl_contract_path: Path,
    opencl_contract_raw: bytes,
    preflight_completion_sha256: str,
    source_revision: str,
) -> dict[str, Any]:
    parent = receipt_path.parent
    expected_local_paths = {
        "preflight_report.json": preflight_report_path,
        "preflight_report.json.sha256": (
            preflight_report_path.with_suffix(".json.sha256")
        ),
        "PREFLIGHT_COMPLETE.json": parent / "PREFLIGHT_COMPLETE.json",
        "opencl_contract.json": opencl_contract_path,
    }
    completion_path = parent / "ADB_CUSTODY_COMPLETE.json"
    sidecar_path = parent / "adb_custody_receipt.json.sha256"
    if (
        receipt_path.name != "adb_custody_receipt.json"
        or preflight_report_path.parent != parent
        or preflight_report_path.name != "preflight_report.json"
        or opencl_contract_path.parent != parent
        or opencl_contract_path.name != "opencl_contract.json"
        or not parent.is_dir()
        or parent.is_symlink()
    ):
        raise AdrenoGateError("ADB custody transaction paths are not canonical")
    for path in [receipt_path, completion_path, sidecar_path, *expected_local_paths.values()]:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or path.is_symlink()
        ):
            raise AdrenoGateError("ADB custody transaction file is unsafe")
    receipt_raw = read_regular(receipt_path)
    receipt_sha256 = sha256_bytes(receipt_raw)
    expected_sidecar = (
        f"{receipt_sha256}  adb_custody_receipt.json\n".encode("ascii")
    )
    validate_regular(
        sidecar_path,
        expected_bytes=len(expected_sidecar),
        expected_sha256=sha256_bytes(expected_sidecar),
    )
    if read_regular(sidecar_path) != expected_sidecar:
        raise AdrenoGateError("ADB custody receipt sidecar drifted")
    receipt = strict_json_decode(receipt_raw, source=str(receipt_path))
    expected_receipt_keys = {
        "schema_version",
        "state",
        "serial",
        "custody_challenge",
        "custody_challenge_generation",
        "utc_run_id",
        "source_revision",
        "device_identity",
        "transport_continuity",
        "boot_id_continuity",
        "remote_paths",
        "invocation_contract",
        "retrieval_contract",
        "artifacts",
        "artifact_set_sha256",
        "timestamps",
        "custody",
        "nonclaims",
    }
    challenge = preflight_report.get("custody_challenge")
    run_id = receipt.get("utc_run_id")
    if (
        set(receipt) != expected_receipt_keys
        or receipt.get("schema_version") != ADB_PREFLIGHT_CUSTODY_SCHEMA
        or receipt.get("state") != "complete"
        or receipt.get("serial") != AUTHORIZED_ADB_SERIAL
        or receipt.get("custody_challenge") != challenge
        or not is_sha256(challenge)
        or receipt.get("source_revision") != source_revision
        or not isinstance(run_id, str)
        or len(run_id) != 22
        or run_id[8] != "T"
        or run_id[-1] != "Z"
        or not (run_id[:8] + run_id[9:-1]).isdigit()
        or receipt.get("custody_challenge_generation")
        != {
            "method": "python_secrets.token_hex",
            "entropy_bytes": 32,
            "lowercase_hex": True,
            "used_once_for_this_transaction": True,
        }
    ):
        raise AdrenoGateError("ADB custody receipt root binding drifted")
    device = receipt.get("device_identity")
    expected_device = {
        "expected_serial": AUTHORIZED_ADB_SERIAL,
        "get_state": "device",
        "get_state_stdout_sha256": sha256_bytes(b"device\n"),
        "get_serialno": AUTHORIZED_ADB_SERIAL,
        "get_serialno_stdout_sha256": sha256_bytes(
            f"{AUTHORIZED_ADB_SERIAL}\n".encode("ascii")
        ),
        "selection": "every_command_uses_explicit_adb_-s_serial",
        "environment_serial_selectors_removed": ["ANDROID_SERIAL", "ADB_SERIAL"],
    }
    if device != expected_device:
        raise AdrenoGateError("authorized ADB device identity drifted")
    ssh_overrides = list(AUTHORIZED_TERMUX_SSH_REQUIRED_OVERRIDES)
    ssh_configuration_argv = [
        "ssh",
        "-G",
        *ssh_overrides,
        AUTHORIZED_TERMUX_SSH_ALIAS,
    ]
    ssh_command_prefix = [
        "ssh",
        *ssh_overrides,
        AUTHORIZED_TERMUX_SSH_ALIAS,
        "--",
    ]
    transport = receipt.get("transport_continuity")
    if not isinstance(transport, dict) or set(transport) != {
        "adb_forward",
        "ssh",
        "remote_identity",
    }:
        raise AdrenoGateError("ADB-forwarded SSH transport shape drifted")
    forward = transport.get("adb_forward")
    expected_mapping_line = (
        f"{AUTHORIZED_ADB_SERIAL} {AUTHORIZED_ADB_FORWARD_LOCAL} "
        f"{AUTHORIZED_ADB_FORWARD_REMOTE}"
    )
    valid_forward = (
        isinstance(forward, dict)
        and set(forward)
        == {
            "verification_argv",
            "expected_mapping_line",
            "local_spec",
            "remote_spec",
            "before_stdout_bytes",
            "before_stdout_sha256",
            "after_stdout_bytes",
            "after_stdout_sha256",
            "stdout_byte_identical",
            "mapping_present_exactly_once_before_and_after",
            "before_observed_at_utc",
            "after_observed_at_utc",
            "forward_created_or_modified_by_wrapper",
        }
        and forward.get("verification_argv")
        == ["adb", "-s", AUTHORIZED_ADB_SERIAL, "forward", "--list"]
        and forward.get("expected_mapping_line") == expected_mapping_line
        and forward.get("local_spec") == AUTHORIZED_ADB_FORWARD_LOCAL
        and forward.get("remote_spec") == AUTHORIZED_ADB_FORWARD_REMOTE
        and isinstance(forward.get("before_stdout_bytes"), int)
        and not isinstance(forward.get("before_stdout_bytes"), bool)
        and forward["before_stdout_bytes"] >= len(expected_mapping_line) + 1
        and forward.get("after_stdout_bytes") == forward["before_stdout_bytes"]
        and is_sha256(forward.get("before_stdout_sha256"))
        and forward.get("after_stdout_sha256")
        == forward.get("before_stdout_sha256")
        and forward.get("stdout_byte_identical") is True
        and forward.get("mapping_present_exactly_once_before_and_after") is True
        and _is_microsecond_utc(forward.get("before_observed_at_utc"))
        and _is_microsecond_utc(forward.get("after_observed_at_utc"))
        and forward.get("forward_created_or_modified_by_wrapper") is False
    )
    if not valid_forward:
        raise AdrenoGateError("authorized ADB forward continuity drifted")
    ssh = transport.get("ssh")
    expected_effective_ssh = {
        "batch_mode": True,
        "password_authentication": False,
        "kbd_interactive_authentication": False,
        "number_of_password_prompts": 0,
        "request_tty": False,
        "strict_host_key_checking": True,
        "identities_only": True,
    }
    valid_ssh = (
        isinstance(ssh, dict)
        and set(ssh)
        == {
            "executable",
            "alias",
            "configuration_argv",
            "required_cli_overrides",
            "command_prefix",
            "resolved_host",
            "resolved_port",
            "resolved_user",
            "resolved_identity_file",
            "client_public_key_fingerprint",
            "resolved_user_known_hosts_file",
            "server_host_key_fingerprint",
            "effective_configuration",
            "before_config_stdout_bytes",
            "before_config_stdout_sha256",
            "after_config_stdout_bytes",
            "after_config_stdout_sha256",
            "config_stdout_byte_identical",
            "before_observed_at_utc",
            "after_observed_at_utc",
        }
        and ssh.get("executable") == "ssh"
        and ssh.get("alias") == AUTHORIZED_TERMUX_SSH_ALIAS
        and ssh.get("configuration_argv") == ssh_configuration_argv
        and ssh.get("required_cli_overrides") == ssh_overrides
        and ssh.get("command_prefix") == ssh_command_prefix
        and ssh.get("resolved_host") == AUTHORIZED_TERMUX_SSH_HOST
        and ssh.get("resolved_port") == AUTHORIZED_TERMUX_SSH_PORT
        and ssh.get("resolved_user") == AUTHORIZED_TERMUX_SSH_USER
        and ssh.get("resolved_identity_file")
        == AUTHORIZED_TERMUX_SSH_IDENTITY_FILE
        and ssh.get("client_public_key_fingerprint")
        == AUTHORIZED_TERMUX_SSH_CLIENT_KEY_FINGERPRINT
        and ssh.get("resolved_user_known_hosts_file")
        == AUTHORIZED_TERMUX_SSH_KNOWN_HOSTS_FILE
        and ssh.get("server_host_key_fingerprint")
        == AUTHORIZED_TERMUX_SSH_SERVER_KEY_FINGERPRINT
        and ssh.get("effective_configuration") == expected_effective_ssh
        and isinstance(ssh.get("before_config_stdout_bytes"), int)
        and not isinstance(ssh.get("before_config_stdout_bytes"), bool)
        and ssh["before_config_stdout_bytes"] > 0
        and ssh.get("after_config_stdout_bytes")
        == ssh["before_config_stdout_bytes"]
        and is_sha256(ssh.get("before_config_stdout_sha256"))
        and ssh.get("after_config_stdout_sha256")
        == ssh.get("before_config_stdout_sha256")
        and ssh.get("config_stdout_byte_identical") is True
        and _is_microsecond_utc(ssh.get("before_observed_at_utc"))
        and _is_microsecond_utc(ssh.get("after_observed_at_utc"))
    )
    if not valid_ssh:
        raise AdrenoGateError("forwarded SSH identity or configuration drifted")
    remote_identity = transport.get("remote_identity")
    valid_remote_identity = (
        isinstance(remote_identity, dict)
        and set(remote_identity)
        == {
            "uid_argv",
            "gid_argv",
            "expected_uid",
            "expected_gid",
            "uid_before",
            "uid_after",
            "gid_before",
            "gid_after",
            "continuous",
            "before_observed_at_utc",
            "after_observed_at_utc",
        }
        and remote_identity.get("uid_argv")
        == [*ssh_command_prefix, "/system/bin/id", "-u"]
        and remote_identity.get("gid_argv")
        == [*ssh_command_prefix, "/system/bin/id", "-g"]
        and remote_identity.get("expected_uid") == AUTHORIZED_TERMUX_UID
        and remote_identity.get("expected_gid") == AUTHORIZED_TERMUX_GID
        and remote_identity.get("uid_before") == AUTHORIZED_TERMUX_UID
        and remote_identity.get("uid_after") == AUTHORIZED_TERMUX_UID
        and remote_identity.get("gid_before") == AUTHORIZED_TERMUX_GID
        and remote_identity.get("gid_after") == AUTHORIZED_TERMUX_GID
        and remote_identity.get("continuous") is True
        and _is_microsecond_utc(remote_identity.get("before_observed_at_utc"))
        and _is_microsecond_utc(remote_identity.get("after_observed_at_utc"))
    )
    if not valid_remote_identity:
        raise AdrenoGateError("forwarded SSH Termux UID/GID continuity drifted")
    boot = receipt.get("boot_id_continuity")
    if (
        not isinstance(boot, dict)
        or set(boot)
        != {
            "source_absolute_path",
            "adb_before",
            "ssh_before",
            "ssh_after",
            "adb_after",
            "all_four_equal",
            "adb_before_observed_at_utc",
            "ssh_before_observed_at_utc",
            "ssh_after_observed_at_utc",
            "adb_after_observed_at_utc",
        }
        or boot.get("source_absolute_path") != "/proc/sys/kernel/random/boot_id"
        or not _is_lower_uuid(boot.get("adb_before"))
        or len(
            {
                boot.get("adb_before"),
                boot.get("ssh_before"),
                boot.get("ssh_after"),
                boot.get("adb_after"),
            }
        )
        != 1
        or boot.get("all_four_equal") is not True
        or not all(
            _is_microsecond_utc(boot.get(name))
            for name in (
                "adb_before_observed_at_utc",
                "ssh_before_observed_at_utc",
                "ssh_after_observed_at_utc",
                "adb_after_observed_at_utc",
            )
        )
    ):
        raise AdrenoGateError("ADB/forwarded-SSH boot continuity drifted")
    remote = receipt.get("remote_paths")
    if not isinstance(remote, dict) or set(remote) != {
        "repository_root",
        "preflight_script",
        "build_parent",
        "build_directory",
        "probe_contract",
        "preflight_report",
        "blocker",
    }:
        raise AdrenoGateError("ADB remote path receipt shape drifted")
    remote_values = list(remote.values())
    if any(
        not isinstance(value, str)
        or not value.startswith("/data/data/com.termux/files/home/")
        or ".." in Path(value).parts
        for value in remote_values
    ):
        raise AdrenoGateError("ADB remote path escaped the phone custody root")
    repository_root = str(remote["repository_root"])
    build_parent = str(remote["build_parent"])
    build_directory = str(remote["build_directory"])
    if (
        remote["preflight_script"]
        != f"{repository_root}/scripts/termux/run_e4b_adreno_int2_preflight.py"
        or Path(build_directory).parent.as_posix() != build_parent
        or remote["probe_contract"] != f"{build_directory}/opencl_contract.json"
        or remote["preflight_report"] != f"{build_directory}/preflight_report.json"
        or remote["blocker"] != f"{build_directory}/PREFLIGHT_BLOCKER.json"
        or run_id not in Path(build_directory).name
        or "_adreno_preflight_adb_forwarded_ssh_"
        not in Path(build_directory).name
        or str(challenge)[:16] not in Path(build_directory).name
    ):
        raise AdrenoGateError("ADB remote path lineage drifted")
    invocation = receipt.get("invocation_contract")
    expected_remote_argv = [
        "/data/data/com.termux/files/usr/bin/env",
        "-i",
        "HOME=/data/data/com.termux/files/home",
        "PATH=/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin",
        "TMPDIR=/data/data/com.termux/files/usr/tmp",
        "LANG=C",
        "LC_ALL=C",
        "TZ=UTC",
        "LD_PRELOAD=/data/data/com.termux/files/usr/lib/libtermux-exec.so",
        "TERMUX_EXEC__PROC_SELF_EXE=/data/data/com.termux/files/usr/bin/python3",
        "/data/data/com.termux/files/usr/bin/python3",
        "-I",
        "-S",
        "-B",
        str(remote["preflight_script"]),
        "--build-dir",
        build_directory,
        "--probe-contract-output",
        str(remote["probe_contract"]),
        "--report",
        str(remote["preflight_report"]),
        "--custody-challenge",
        str(challenge),
    ]
    valid_invocation = (
        isinstance(invocation, dict)
        and set(invocation)
        == {
            "ssh_argv",
            "remote_argv",
            "host_shell_used",
            "stdin_transport",
            "timeout_seconds",
            "return_code",
            "stdout_bytes",
            "stdout_sha256",
            "stderr_bytes",
            "stderr_sha256",
        }
        and invocation.get("remote_argv") == expected_remote_argv
        and invocation.get("ssh_argv")
        == [*ssh_command_prefix, *expected_remote_argv]
        and invocation.get("host_shell_used") is False
        and invocation.get("stdin_transport") == "DEVNULL"
        and invocation.get("timeout_seconds") == 1_800
        and invocation.get("return_code") == 0
        and invocation.get("stdout_bytes") == 0
        and invocation.get("stdout_sha256") == sha256_bytes(b"")
        and invocation.get("stderr_bytes") == 0
        and invocation.get("stderr_sha256") == sha256_bytes(b"")
    )
    if not valid_invocation:
        raise AdrenoGateError("ADB preflight invocation contract drifted")
    retrieval = receipt.get("retrieval_contract")
    artifact_names = [
        "preflight_report.json",
        "preflight_report.json.sha256",
        "PREFLIGHT_COMPLETE.json",
        "opencl_contract.json",
    ]
    expected_inventory = [
        "PREFLIGHT_COMPLETE.json",
        "build_a",
        "build_b",
        "opencl_contract.json",
        "preflight_report.json",
        "preflight_report.json.sha256",
        "probe.stderr.log",
        "probe.stdout.log",
    ]
    valid_retrieval = (
        isinstance(retrieval, dict)
        and set(retrieval)
        == {
            "method",
            "ssh_command_prefix",
            "allowlisted_artifact_names",
            "every_retrieval_used_exact_absolute_path",
            "blocker_path_absent",
            "remote_top_level_inventory",
            "raw_model_tensor_or_candidate_path_requested",
            "scp_used",
            "direct_adb_shell_used",
        }
        and retrieval.get("method")
        == (
            "verified_explicit_ADB_forward_plus_forwarded_SSH_"
            "/system/bin/cat_exact_path"
        )
        and retrieval.get("ssh_command_prefix") == ssh_command_prefix
        and retrieval.get("allowlisted_artifact_names") == artifact_names
        and retrieval.get("every_retrieval_used_exact_absolute_path") is True
        and retrieval.get("blocker_path_absent") is True
        and retrieval.get("remote_top_level_inventory") == expected_inventory
        and retrieval.get("raw_model_tensor_or_candidate_path_requested") is False
        and retrieval.get("scp_used") is False
        and retrieval.get("direct_adb_shell_used") is False
    )
    if not valid_retrieval:
        raise AdrenoGateError("ADB preflight retrieval contract drifted")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(artifact_names):
        raise AdrenoGateError("ADB custody artifact inventory drifted")
    artifact_remote_paths = {
        "preflight_report.json": str(remote["preflight_report"]),
        "preflight_report.json.sha256": f"{remote['preflight_report']}.sha256",
        "PREFLIGHT_COMPLETE.json": f"{build_directory}/PREFLIGHT_COMPLETE.json",
        "opencl_contract.json": str(remote["probe_contract"]),
    }
    for name, local_path in expected_local_paths.items():
        payload = read_regular(local_path)
        record = artifacts.get(name)
        if (
            not isinstance(record, dict)
            or set(record)
            != {
                "remote_absolute_path",
                "local_filename",
                "bytes",
                "sha256",
                "retrieved_at_utc",
            }
            or record.get("remote_absolute_path") != artifact_remote_paths[name]
            or record.get("local_filename") != name
            or record.get("bytes") != len(payload)
            or record.get("sha256") != sha256_bytes(payload)
            or not _is_microsecond_utc(record.get("retrieved_at_utc"))
        ):
            raise AdrenoGateError("ADB custody artifact binding drifted")
    if receipt.get("artifact_set_sha256") != sha256_bytes(canonical_json(artifacts)):
        raise AdrenoGateError("ADB custody artifact-set digest drifted")
    if artifacts["preflight_report.json"]["sha256"] != sha256_bytes(
        preflight_report_raw
    ) or artifacts["opencl_contract.json"]["sha256"] != sha256_bytes(
        opencl_contract_raw
    ):
        raise AdrenoGateError("ADB custody principal artifact digest drifted")
    if (
        artifacts["PREFLIGHT_COMPLETE.json"]["sha256"]
        != preflight_completion_sha256
    ):
        raise AdrenoGateError("ADB custody preflight completion digest drifted")
    timestamps = receipt.get("timestamps")
    timestamp_names = [
        "wrapper_started_at_utc",
        "device_identity_verified_at_utc",
        "transport_before_verified_at_utc",
        "preflight_started_at_utc",
        "preflight_completed_at_utc",
        "retrieval_started_at_utc",
        "retrieval_completed_at_utc",
        "inventory_observed_at_utc",
        "transport_after_verified_at_utc",
        "receipt_sealed_at_utc",
    ]
    if (
        not isinstance(timestamps, dict)
        or set(timestamps) != set(timestamp_names)
        or not all(_is_microsecond_utc(timestamps[name]) for name in timestamp_names)
        or [timestamps[name] for name in timestamp_names]
        != sorted(timestamps[name] for name in timestamp_names)
    ):
        raise AdrenoGateError("ADB custody timestamp sequence drifted")
    expected_custody = {
        "source_neutral_artifacts_only": True,
        "retrieval_allowlist_fixed_in_source": True,
        "local_directory_atomic_noreplace_publication": True,
        "raw_model_tensor_or_candidate_data_retrieved": False,
        "termux_execution_via_forwarded_ssh_only": True,
        "direct_adb_shell_used": False,
        "adb_forward_created_or_modified": False,
        "scp_used": False,
    }
    expected_nonclaims = [
        "no_hardware_attestation",
        "no_resistance_to_malicious_same-UID_compromise",
        "no_kernel_level_ADB_or_SSH_transport_attestation",
        "no_raw_model_tensor_or_candidate_payload_custody_claim",
    ]
    if receipt.get("custody") != expected_custody or receipt.get(
        "nonclaims"
    ) != expected_nonclaims:
        raise AdrenoGateError("ADB custody claim boundary drifted")
    completion_raw = read_regular(completion_path)
    completion = strict_json_decode(completion_raw, source=str(completion_path))
    expected_completion = {
        "schema_version": ADB_PREFLIGHT_CUSTODY_COMPLETION_SCHEMA,
        "state": "complete",
        "receipt_sha256": receipt_sha256,
        "artifact_set_sha256": receipt["artifact_set_sha256"],
        "serial": AUTHORIZED_ADB_SERIAL,
        "custody_challenge": challenge,
        "boot_id": boot["adb_before"],
        "remote_build_directory": build_directory,
        "source_revision": source_revision,
    }
    if completion != expected_completion:
        raise AdrenoGateError("ADB custody completion marker drifted")
    if sha256_bytes(completion_raw) == preflight_completion_sha256:
        raise AdrenoGateError("ADB and preflight completion artifacts were conflated")
    return {
        "schema_version": ADB_PREFLIGHT_CUSTODY_SCHEMA,
        "receipt_sha256": receipt_sha256,
        "completion_sha256": sha256_bytes(completion_raw),
        "artifact_set_sha256": receipt["artifact_set_sha256"],
        "serial": AUTHORIZED_ADB_SERIAL,
        "transport": "explicit_ADB_forward_plus_forwarded_SSH",
        "custody_challenge": challenge,
        "boot_id": boot["adb_before"],
        "remote_build_directory": build_directory,
        "source_revision": source_revision,
        "hardware_attestation": False,
        "direct_adb_shell_used": False,
    }


def build_preregistration(
    *,
    repository_root: Path,
    frontier_selector_path: Path,
    s16_falsification_path: Path,
    opencl_evidence_report_path: Path,
    opencl_contract_path: Path,
    source_neutral_preflight_report_path: Path,
    adb_custody_receipt_path: Path,
    output_dir: Path,
    created_at_utc: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    s16_raw = read_regular(s16_falsification_path)
    if sha256_bytes(s16_raw) != FROZEN_S16_FALSIFICATION_SHA256:
        raise AdrenoGateError("S16 falsification ancestor digest drifted")
    s16 = strict_json_decode(s16_raw, source=str(s16_falsification_path))
    _validate_s16_falsification(s16)
    selector_raw = read_regular(frontier_selector_path)
    if sha256_bytes(selector_raw) != FROZEN_FRONTIER_SELECTOR_SHA256:
        raise AdrenoGateError("frontier selector ancestor digest drifted")
    selector = strict_json_decode(selector_raw, source=str(frontier_selector_path))
    selected_contract = selector.get("immutable_candidate_contract")
    if selector.get("schema_version") != "gemma4_e4b_frontier_event_v1":
        raise AdrenoGateError("frontier selector schema mismatch")
    if selector.get("state") != "selected" or not isinstance(selected_contract, dict):
        raise AdrenoGateError("frontier selector is not selected")
    if selected_contract.get("candidate_id") != CANDIDATE_ID:
        raise AdrenoGateError("frontier selector candidate mismatch")
    if selector.get("phone_execution_started") is not False:
        raise AdrenoGateError("frontier selector is no longer unexecuted")
    if selector.get("candidate_output_observed") is not False:
        raise AdrenoGateError("frontier selector contains candidate output")
    _validate_frontier_selector(selector)
    opencl_evidence_raw = read_regular(opencl_evidence_report_path)
    if sha256_bytes(opencl_evidence_raw) != FROZEN_OPENCL_EVIDENCE_SHA256:
        raise AdrenoGateError("OpenCL evidence ancestor digest drifted")
    opencl_evidence = _validate_opencl_evidence(
        strict_json_decode(
            opencl_evidence_raw, source=str(opencl_evidence_report_path)
        ),
        selector,
        sha256_bytes(opencl_evidence_raw),
    )
    opencl_raw = read_regular(opencl_contract_path)
    opencl = normalize_opencl_contract(
        strict_json_decode(opencl_raw, source=str(opencl_contract_path))
    )
    opencl_source_sha256 = sha256_bytes(opencl_raw)
    opencl_canonical_sha256 = sha256_bytes(canonical_json(opencl))
    opencl_evidence = {
        **opencl_evidence,
        "execution_contract_source_sha256": opencl_source_sha256,
        "execution_contract_canonical_sha256": opencl_canonical_sha256,
        "execution_contract_generator_relative_path": (
            "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp"
        ),
    }
    thresholds = frozen_thresholds()
    source_revision, closure = source_closure(repository_root)
    preflight_raw = read_regular(source_neutral_preflight_report_path)
    preflight = strict_json_decode(
        preflight_raw, source=str(source_neutral_preflight_report_path)
    )
    preflight_completion_sha256 = _validate_source_neutral_preflight_transaction(
        source_neutral_preflight_report_path, preflight_raw, preflight
    )
    native_binary_bytes, native_binary_sha256 = _validate_source_neutral_preflight(
        preflight,
        source_revision=source_revision,
        closure=closure,
        opencl_raw=opencl_raw,
        opencl=opencl,
    )
    adb_custody = _validate_adb_custody_receipt_transaction(
        adb_custody_receipt_path,
        preflight_report_path=source_neutral_preflight_report_path,
        preflight_report_raw=preflight_raw,
        preflight_report=preflight,
        opencl_contract_path=opencl_contract_path,
        opencl_contract_raw=opencl_raw,
        preflight_completion_sha256=preflight_completion_sha256,
        source_revision=source_revision,
    )
    source_closure_sha256 = sha256_bytes(canonical_json(closure))
    if opencl.get("source_closure_sha256") != source_closure_sha256:
        raise AdrenoGateError("OpenCL binary source closure witness drifted")
    preregistration = {
        "schema_version": PREREGISTRATION_SCHEMA,
        "state": "frozen_unobserved",
        "created_at_utc": created_at_utc,
        "candidate_id": CANDIDATE_ID,
        "candidate_output_observed": False,
        "candidate_output_observation_scope": (
            "this_preregistration_lineage_and_ADB_forwarded_SSH_custody_run_only"
        ),
        "phone_execution_count": 0,
        "frontier_selector_sha256": sha256_bytes(selector_raw),
        "parent_frontier_root_sha256": selector["parent_frontier_root_sha256"],
        "parent_capsule_sha256": selector["parent_capsule_sha256"],
        "mandatory_predecessor": {
            "schema_version": S16_FALSIFICATION_SCHEMA,
            "sha256": sha256_bytes(s16_raw),
            "oracle_gate_sha256": s16["governing_bindings"]["oracle_gate_sha256"],
            "status": "falsified_scope",
            "standard_htp_s16_family_exhausted": True,
        },
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "bytes": MODEL_BYTES,
            "sha256": MODEL_SHA256,
            "raw_location": "phone_private_authority",
            "execution_dependency": False,
            "role": "immutable_lineage_only_runtime_uses_exact_extracted_tensors",
        },
        "tensor_contract": {
            "packed_weight": {
                "dtype": "U8",
                "logical_shape": [OUTPUT_FEATURES, INPUT_FEATURES],
                "storage_shape": [OUTPUT_FEATURES, PACKED_BYTES_PER_ROW],
                "absolute_offset": PACKED_WEIGHT_ABSOLUTE_OFFSET,
                "bytes": PACKED_WEIGHT_BYTES,
                "sha256": PACKED_WEIGHT_SHA256,
                "lane_mapping": [-2, -1, 0, 1],
                "bits_per_weight": 2,
                "dense_expansion_forbidden": True,
                "runtime_source": "phone_private_hash_bound_regular_file",
            },
            "row_scale": {
                "source_dtype": "F32",
                "shape": [OUTPUT_FEATURES, 1],
                "absolute_offset": SCALE_ABSOLUTE_OFFSET,
                "source_bytes": SCALE_F32_BYTES,
                "source_sha256": SCALE_F32_SHA256,
                "transform": "F32_to_BF16_RNE",
                "transformed_exact_f32_sha256": SCALE_BF16_RNE_AS_F32_SHA256,
                "gpu_dtype": "BF16_bits_in_U16",
                "gpu_bytes": SCALE_BF16_BYTES,
                "runtime_source": "phone_private_hash_bound_regular_file",
            },
        },
        "kernel_contract": {
            "input_dtype": "BF16_bits_in_U16",
            "output_dtype": "BF16_bits_in_U16",
            "weight_dequantization": (
                "signed_INT2_code_times_BF16_RNE_row_scale_then_BF16_RNE_weight"
            ),
            "product": "exact_FP32_product_of_two_BF16_operands",
            "accumulation": (
                "four_ascending_10_term_FP32_lane_chains_pairwise_combined_then_"
                "fixed_local_tree_strides_32_16_8_4_2_1"
            ),
            "output_rounding": "explicit_BF16_RNE_bits",
            "local_size": LOCAL_SIZE,
            "rows_per_workgroup": ROWS_PER_WORKGROUP,
            "workgroup_count": WORKGROUP_COUNT,
            "global_size": WORKGROUP_COUNT * LOCAL_SIZE,
            "dense_weight_expansion": False,
            "fast_relaxed_math": False,
            "fp_contract": False,
        },
        "residency_and_replay": {
            "process_count": 1,
            "context_count": 1,
            "program_build_count": 1,
            "packed_weight_upload_count": 1,
            "scale_upload_count": 1,
            "authority_case_count": 3,
            "sentinel_case_count": 1,
            "replays_per_case": REPLAY_COUNT_PER_CASE,
            "dispatch_count": DISPATCH_COUNT,
            "replay_must_be_byte_identical": True,
        },
        "opencl_contract": opencl,
        "opencl_contract_source_sha256": opencl_source_sha256,
        "opencl_contract_canonical_sha256": opencl_canonical_sha256,
        "opencl_evidence": opencl_evidence,
        "toolchain_contract": toolchain_contract(),
        "native_binary_contract": {
            "preflight_bytes": native_binary_bytes,
            "preflight_sha256": native_binary_sha256,
            "preflight_report_schema": SOURCE_NEUTRAL_PREFLIGHT_SCHEMA,
            "preflight_report_sha256": sha256_bytes(preflight_raw),
            "preflight_completion_sha256": preflight_completion_sha256,
            "source_neutral_preflight": True,
            "candidate_rebuild_must_be_byte_identical": True,
            "candidate_output_observed": False,
        },
        "adb_preflight_custody": adb_custody,
        "required_device_extensions": list(REQUIRED_DEVICE_EXTENSIONS),
        "cases": _case_contracts(),
        "off_s16_lattice_sentinel": {
            "case_id": SENTINEL_CASE_ID,
            "purpose": "reject_exact_INT32_or_S16_lattice_specialization",
            "construction": "all_zero_BF16_except_feature_0_equal_to_0x3a80_2m10",
            "nonzero_feature_index": 0,
            "nonzero_value_bfloat16_bits": "0x3a80",
            "input_dtype": "BF16_bits_in_U16",
            "input_bytes": INPUT_BYTES,
            "input_sha256": SENTINEL_INPUT_SHA256,
            "input_relative_path": f"private_inputs/{SENTINEL_CASE_ID}.bf16.raw",
            "contains_value_off_s16_2m9_lattice": True,
            "reference_rule": "full_width_single_product_exact_BF16_semantics",
            "authority_metric_gate": False,
            "replay_output_relative_paths": [
                f"private_outputs/{SENTINEL_CASE_ID}.replay0.bf16.raw",
                f"private_outputs/{SENTINEL_CASE_ID}.replay1.bf16.raw",
            ],
            "replay_must_be_byte_identical": True,
            "candidate_output_present": False,
        },
        "numeric_and_ranking_thresholds": thresholds,
        "thresholds_sha256": sha256_bytes(canonical_json(thresholds)),
        "source_binding": {
            "repository": "Zer0pa/Polymath-AI",
            "revision": source_revision,
            "head_equals_revision": True,
            "every_closure_file_matches_head_blob": True,
            "every_closure_file_matches_head_mode": True,
            "closure_sha256": source_closure_sha256,
        },
        "source_closure": closure,
        "phone_execution_envelope": {
            "execution_plane": "phone_native_termux",
            "raw_inputs_outputs_and_tensors": "phone_private_no_egress",
            "sanitized_hash_bound_receipt_only": True,
            "thermal_sensor_type": "pmih010x_lite_tz",
            "thermal_stop_at_or_above_millidegrees_c": 90_000,
            "minimum_available_memory_bytes": 2_147_483_648,
            "minimum_available_storage_bytes": 2_147_483_648,
            "maximum_wall_time_seconds": 14_400,
        },
        "failure_rule": (
            "falsify_this_OpenCL_candidate_without_threshold_relaxation_if_any_case_metric_"
            "replay_runtime_source_or_tensor_contract_fails"
        ),
        "custody": {
            "raw_model_weight_input_reference_and_candidate_egress": False,
            "raw_phone_private_upload_to_provider": False,
            "repository_or_comet_raw_payload_storage": False,
            "sanitized_hash_bound_metadata_only": True,
        },
        "nonclaims": [
            "no_OpenCL_candidate_output_observed_in_this_preregistration_lineage_and_ADB_forwarded_SSH_custody_run",
            "no_global_historical_candidate_observation_claim",
            "no_hardware_attestation",
            "no_resistance_to_malicious_same_UID_or_fully_compromised_phone",
            "no_full_L1_or_L2_pass",
            "no_learning_or_authority_quality_pass",
            "no_performance_claim_before_authority_fidelity",
        ],
    }
    _publish_preregistration_directory(output_dir, preregistration)
    return preregistration


def validate_source_closure(root: Path, preregistration: Mapping[str, Any]) -> None:
    binding = preregistration.get("source_binding")
    if not isinstance(binding, dict):
        raise AdrenoGateError("source binding is absent")
    revision = binding.get("revision")
    if binding.get("repository") != "Zer0pa/Polymath-AI" or not isinstance(
        revision, str
    ):
        raise AdrenoGateError("source repository or revision binding mismatch")
    if _git_output(root, "rev-parse", "HEAD") != revision:
        raise AdrenoGateError("execution checkout HEAD drifted from preregistration")
    records = preregistration.get("source_closure")
    if not isinstance(records, list) or not records:
        raise AdrenoGateError("source closure is empty")
    expected = set(SOURCE_CLOSURE)
    observed: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise AdrenoGateError("invalid source closure record")
        relative = record.get("relative_path")
        if (
            not isinstance(relative, str)
            or relative not in expected
            or relative in observed
        ):
            raise AdrenoGateError("source closure path mismatch")
        path = resolve_relative(root, relative)
        validate_regular(
            path,
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )
        head_blob = _git_output(root, "rev-parse", f"HEAD:{relative}")
        head_mode, tree_blob = _git_tree_entry(root, revision, relative)
        working_blob = _git_output(root, "hash-object", "--", relative)
        working_mode = _working_git_mode(path)
        if (
            record.get("git_blob_oid") != head_blob
            or tree_blob != head_blob
            or working_blob != head_blob
        ):
            raise AdrenoGateError("execution source blob drifted")
        if record.get("git_mode") != head_mode or working_mode != head_mode:
            raise AdrenoGateError("execution source mode drifted")
        if relative in SOURCE_EXECUTABLES and (
            head_mode != "100755" or not os.access(path, os.X_OK)
        ):
            raise AdrenoGateError("required execution source is not executable")
        observed.add(relative)
    if observed != expected:
        raise AdrenoGateError("source closure is incomplete")


def validate_preregistration(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != PREREGISTRATION_SCHEMA:
        raise AdrenoGateError("preregistration schema mismatch")
    if payload.get("state") != "frozen_unobserved":
        raise AdrenoGateError("preregistration is not frozen-unobserved")
    if payload.get("candidate_id") != CANDIDATE_ID:
        raise AdrenoGateError("candidate identity mismatch")
    if payload.get("candidate_output_observed") is not False:
        raise AdrenoGateError("preregistration contains candidate observations")
    if (
        payload.get("candidate_output_observation_scope")
        != "this_preregistration_lineage_and_ADB_forwarded_SSH_custody_run_only"
    ):
        raise AdrenoGateError("preregistration candidate observation scope drifted")
    if payload.get("phone_execution_count") != 0:
        raise AdrenoGateError("preregistration phone execution count is not zero")
    expected_ancestry = {
        "frontier_selector_sha256": FROZEN_FRONTIER_SELECTOR_SHA256,
        "parent_frontier_root_sha256": FROZEN_PARENT_FRONTIER_ROOT_SHA256,
        "parent_capsule_sha256": FROZEN_PARENT_CAPSULE_SHA256,
    }
    for field, expected in expected_ancestry.items():
        if payload.get(field) != expected:
            raise AdrenoGateError(f"preregistration {field} drifted")
    if payload.get("numeric_and_ranking_thresholds") != FROZEN_THRESHOLDS:
        raise AdrenoGateError("preregistered thresholds drifted")
    if payload.get("thresholds_sha256") != sha256_bytes(
        canonical_json(FROZEN_THRESHOLDS)
    ):
        raise AdrenoGateError("threshold digest mismatch")
    normalized_opencl = normalize_opencl_contract(payload.get("opencl_contract", {}))
    source_contract_sha256 = payload.get("opencl_contract_source_sha256")
    canonical_contract_sha256 = payload.get("opencl_contract_canonical_sha256")
    if (
        not isinstance(source_contract_sha256, str)
        or len(source_contract_sha256) != 64
        or any(
            character not in "0123456789abcdef" for character in source_contract_sha256
        )
    ):
        raise AdrenoGateError("OpenCL execution contract source digest is invalid")
    if canonical_contract_sha256 != sha256_bytes(canonical_json(normalized_opencl)):
        raise AdrenoGateError("OpenCL execution contract canonical digest drifted")
    model = payload.get("model")
    expected_model = {
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "bytes": MODEL_BYTES,
        "sha256": MODEL_SHA256,
        "raw_location": "phone_private_authority",
        "execution_dependency": False,
        "role": "immutable_lineage_only_runtime_uses_exact_extracted_tensors",
    }
    if model != expected_model:
        raise AdrenoGateError("model lineage contract drifted")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise AdrenoGateError("exactly three cases are required")
    expected_cases = _case_contracts()
    if cases != expected_cases:
        raise AdrenoGateError("case contract drifted")
    sentinel = payload.get("off_s16_lattice_sentinel")
    if not isinstance(sentinel, dict):
        raise AdrenoGateError("off-S16-lattice sentinel is absent")
    if sentinel.get("input_sha256") != SENTINEL_INPUT_SHA256:
        raise AdrenoGateError("off-S16-lattice sentinel drifted")
    expected_sentinel = {
        "case_id": SENTINEL_CASE_ID,
        "purpose": "reject_exact_INT32_or_S16_lattice_specialization",
        "construction": "all_zero_BF16_except_feature_0_equal_to_0x3a80_2m10",
        "nonzero_feature_index": 0,
        "nonzero_value_bfloat16_bits": "0x3a80",
        "input_dtype": "BF16_bits_in_U16",
        "input_bytes": INPUT_BYTES,
        "input_sha256": SENTINEL_INPUT_SHA256,
        "input_relative_path": f"private_inputs/{SENTINEL_CASE_ID}.bf16.raw",
        "contains_value_off_s16_2m9_lattice": True,
        "reference_rule": "full_width_single_product_exact_BF16_semantics",
        "authority_metric_gate": False,
        "replay_output_relative_paths": [
            f"private_outputs/{SENTINEL_CASE_ID}.replay0.bf16.raw",
            f"private_outputs/{SENTINEL_CASE_ID}.replay1.bf16.raw",
        ],
        "replay_must_be_byte_identical": True,
        "candidate_output_present": False,
    }
    if sentinel != expected_sentinel:
        raise AdrenoGateError("off-S16-lattice sentinel contract drifted")
    tensor = payload.get("tensor_contract")
    if not isinstance(tensor, dict):
        raise AdrenoGateError("tensor contract missing")
    packed = tensor.get("packed_weight")
    if (
        not isinstance(packed, dict)
        or packed.get("dense_expansion_forbidden") is not True
    ):
        raise AdrenoGateError("direct-packed invariant missing")
    expected_packed = {
        "dtype": "U8",
        "logical_shape": [OUTPUT_FEATURES, INPUT_FEATURES],
        "storage_shape": [OUTPUT_FEATURES, PACKED_BYTES_PER_ROW],
        "absolute_offset": PACKED_WEIGHT_ABSOLUTE_OFFSET,
        "bytes": PACKED_WEIGHT_BYTES,
        "sha256": PACKED_WEIGHT_SHA256,
        "lane_mapping": [-2, -1, 0, 1],
        "bits_per_weight": 2,
        "dense_expansion_forbidden": True,
        "runtime_source": "phone_private_hash_bound_regular_file",
    }
    expected_scale = {
        "source_dtype": "F32",
        "shape": [OUTPUT_FEATURES, 1],
        "absolute_offset": SCALE_ABSOLUTE_OFFSET,
        "source_bytes": SCALE_F32_BYTES,
        "source_sha256": SCALE_F32_SHA256,
        "transform": "F32_to_BF16_RNE",
        "transformed_exact_f32_sha256": SCALE_BF16_RNE_AS_F32_SHA256,
        "gpu_dtype": "BF16_bits_in_U16",
        "gpu_bytes": SCALE_BF16_BYTES,
        "runtime_source": "phone_private_hash_bound_regular_file",
    }
    if packed != expected_packed or tensor.get("row_scale") != expected_scale:
        raise AdrenoGateError("tensor contract drifted")
    kernel = payload.get("kernel_contract")
    expected_kernel = {
        "input_dtype": "BF16_bits_in_U16",
        "output_dtype": "BF16_bits_in_U16",
        "weight_dequantization": (
            "signed_INT2_code_times_BF16_RNE_row_scale_then_BF16_RNE_weight"
        ),
        "product": "exact_FP32_product_of_two_BF16_operands",
        "accumulation": (
            "four_ascending_10_term_FP32_lane_chains_pairwise_combined_then_"
            "fixed_local_tree_strides_32_16_8_4_2_1"
        ),
        "output_rounding": "explicit_BF16_RNE_bits",
        "local_size": LOCAL_SIZE,
        "rows_per_workgroup": ROWS_PER_WORKGROUP,
        "workgroup_count": WORKGROUP_COUNT,
        "global_size": WORKGROUP_COUNT * LOCAL_SIZE,
        "dense_weight_expansion": False,
        "fast_relaxed_math": False,
        "fp_contract": False,
    }
    if kernel != expected_kernel:
        raise AdrenoGateError("kernel arithmetic contract drifted")
    expected_residency = {
        "process_count": 1,
        "context_count": 1,
        "program_build_count": 1,
        "packed_weight_upload_count": 1,
        "scale_upload_count": 1,
        "authority_case_count": 3,
        "sentinel_case_count": 1,
        "replays_per_case": REPLAY_COUNT_PER_CASE,
        "dispatch_count": DISPATCH_COUNT,
        "replay_must_be_byte_identical": True,
    }
    if payload.get("residency_and_replay") != expected_residency:
        raise AdrenoGateError("residency and replay contract drifted")
    toolchain = payload.get("toolchain_contract")
    expected_toolchain = toolchain_contract()
    if toolchain != expected_toolchain:
        raise AdrenoGateError("toolchain contract drifted")
    native_binary = payload.get("native_binary_contract")
    if (
        not isinstance(native_binary, dict)
        or set(native_binary)
        != {
            "preflight_bytes",
            "preflight_sha256",
            "preflight_report_schema",
            "preflight_report_sha256",
            "preflight_completion_sha256",
            "source_neutral_preflight",
            "candidate_rebuild_must_be_byte_identical",
            "candidate_output_observed",
        }
        or isinstance(native_binary.get("preflight_bytes"), bool)
        or not isinstance(native_binary.get("preflight_bytes"), int)
        or native_binary["preflight_bytes"] <= 0
        or not is_sha256(native_binary.get("preflight_sha256"))
        or native_binary.get("preflight_report_schema")
        != SOURCE_NEUTRAL_PREFLIGHT_SCHEMA
        or not is_sha256(native_binary.get("preflight_report_sha256"))
        or not is_sha256(native_binary.get("preflight_completion_sha256"))
        or native_binary.get("source_neutral_preflight") is not True
        or native_binary.get("candidate_rebuild_must_be_byte_identical") is not True
        or native_binary.get("candidate_output_observed") is not False
    ):
        raise AdrenoGateError("native binary contract drifted")
    adb_custody = payload.get("adb_preflight_custody")
    if (
        not isinstance(adb_custody, dict)
        or set(adb_custody)
        != {
            "schema_version",
            "receipt_sha256",
            "completion_sha256",
            "artifact_set_sha256",
            "serial",
            "transport",
            "custody_challenge",
            "boot_id",
            "remote_build_directory",
            "source_revision",
            "hardware_attestation",
            "direct_adb_shell_used",
        }
        or adb_custody.get("schema_version") != ADB_PREFLIGHT_CUSTODY_SCHEMA
        or not is_sha256(adb_custody.get("receipt_sha256"))
        or not is_sha256(adb_custody.get("completion_sha256"))
        or not is_sha256(adb_custody.get("artifact_set_sha256"))
        or adb_custody.get("serial") != AUTHORIZED_ADB_SERIAL
        or adb_custody.get("transport")
        != "explicit_ADB_forward_plus_forwarded_SSH"
        or adb_custody.get("custody_challenge")
        != normalized_opencl.get("custody_challenge")
        or not _is_lower_uuid(adb_custody.get("boot_id"))
        or not isinstance(adb_custody.get("remote_build_directory"), str)
        or not str(adb_custody["remote_build_directory"]).startswith(
            "/data/data/com.termux/files/home/"
        )
        or adb_custody.get("hardware_attestation") is not False
        or adb_custody.get("direct_adb_shell_used") is not False
    ):
        raise AdrenoGateError("ADB preflight custody binding drifted")
    evidence = payload.get("opencl_evidence")
    if not isinstance(evidence, dict):
        raise AdrenoGateError("OpenCL evidence binding is absent")
    expected_evidence = {
        "report_sha256": FROZEN_OPENCL_EVIDENCE_SHA256,
        "android_build_fingerprint_stdout_sha256": (
            ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": [dict(item) for item in VENDOR_RUNTIME_FILES],
        "execution_contract_source_sha256": source_contract_sha256,
        "execution_contract_canonical_sha256": canonical_contract_sha256,
        "execution_contract_generator_relative_path": (
            "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp"
        ),
    }
    if evidence != expected_evidence:
        raise AdrenoGateError("OpenCL evidence runtime binding drifted")
    binding = payload.get("source_binding")
    if not isinstance(binding, dict):
        raise AdrenoGateError("source binding is absent")
    if binding.get("repository") != "Zer0pa/Polymath-AI":
        raise AdrenoGateError("source repository binding drifted")
    revision = binding.get("revision")
    if (
        not isinstance(revision, str)
        or len(revision) not in {40, 64}
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise AdrenoGateError("source revision binding is invalid")
    if adb_custody.get("source_revision") != revision:
        raise AdrenoGateError("ADB custody source revision drifted")
    if (
        binding.get("head_equals_revision") is not True
        or binding.get("every_closure_file_matches_head_blob") is not True
        or binding.get("every_closure_file_matches_head_mode") is not True
        or binding.get("closure_sha256")
        != sha256_bytes(canonical_json(payload.get("source_closure")))
    ):
        raise AdrenoGateError("source cleanliness binding drifted")
    expected_envelope = {
        "execution_plane": "phone_native_termux",
        "raw_inputs_outputs_and_tensors": "phone_private_no_egress",
        "sanitized_hash_bound_receipt_only": True,
        "thermal_sensor_type": "pmih010x_lite_tz",
        "thermal_stop_at_or_above_millidegrees_c": 90_000,
        "minimum_available_memory_bytes": 2_147_483_648,
        "minimum_available_storage_bytes": 2_147_483_648,
        "maximum_wall_time_seconds": 14_400,
    }
    if payload.get("phone_execution_envelope") != expected_envelope:
        raise AdrenoGateError("phone execution envelope drifted")
    expected_custody = {
        "raw_model_weight_input_reference_and_candidate_egress": False,
        "raw_phone_private_upload_to_provider": False,
        "repository_or_comet_raw_payload_storage": False,
        "sanitized_hash_bound_metadata_only": True,
    }
    if payload.get("custody") != expected_custody:
        raise AdrenoGateError("phone custody contract drifted")
    expected_failure_rule = (
        "falsify_this_OpenCL_candidate_without_threshold_relaxation_if_any_case_metric_"
        "replay_runtime_source_or_tensor_contract_fails"
    )
    if payload.get("failure_rule") != expected_failure_rule:
        raise AdrenoGateError("failure rule drifted")
    expected_predecessor = {
        "schema_version": S16_FALSIFICATION_SCHEMA,
        "sha256": FROZEN_S16_FALSIFICATION_SHA256,
        "oracle_gate_sha256": S16_ORACLE_GATE_SHA256,
        "status": "falsified_scope",
        "standard_htp_s16_family_exhausted": True,
    }
    if payload.get("mandatory_predecessor") != expected_predecessor:
        raise AdrenoGateError("mandatory predecessor binding drifted")
    if payload.get("required_device_extensions") != list(REQUIRED_DEVICE_EXTENSIONS):
        raise AdrenoGateError("required device extensions drifted")
    expected_nonclaims = [
        "no_OpenCL_candidate_output_observed_in_this_preregistration_lineage_and_ADB_forwarded_SSH_custody_run",
        "no_global_historical_candidate_observation_claim",
        "no_hardware_attestation",
        "no_resistance_to_malicious_same_UID_or_fully_compromised_phone",
        "no_full_L1_or_L2_pass",
        "no_learning_or_authority_quality_pass",
        "no_performance_claim_before_authority_fidelity",
    ]
    if payload.get("nonclaims") != expected_nonclaims:
        raise AdrenoGateError("preregistration nonclaim boundary drifted")


def runtime_environment(opencl_contract: Mapping[str, Any]) -> dict[str, str]:
    normalized = normalize_opencl_contract(opencl_contract)
    identity = normalized["identity"]
    loader = normalized["loader"]
    names = {
        "POLYMATH_EXPECT_OPENCL_LOADED_PATH": loader["loaded_path"],
        "POLYMATH_EXPECT_OPENCL_LOAD_ROUTE": loader["route"],
        "POLYMATH_EXPECT_OPENCL_PLATFORM_NAME": identity["platform_name"],
        "POLYMATH_EXPECT_OPENCL_PLATFORM_VENDOR": identity["platform_vendor"],
        "POLYMATH_EXPECT_OPENCL_PLATFORM_VERSION": identity["platform_version"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_NAME": identity["device_name"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_VENDOR": identity["device_vendor"],
        "POLYMATH_EXPECT_OPENCL_DRIVER_VERSION": identity["driver_version"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_VERSION": identity["device_version"],
        "POLYMATH_EXPECT_OPENCL_C_VERSION": identity["opencl_c_version"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_EXTENSIONS": identity["device_extensions"],
    }
    return {key: str(value) for key, value in names.items()}


__all__ = [
    "AdrenoGateError",
    "CANDIDATE_ID",
    "FROZEN_CASES",
    "FROZEN_THRESHOLDS",
    "INPUT_BYTES",
    "MODEL_BYTES",
    "MODEL_SHA256",
    "OUTPUT_BYTES",
    "PACKED_WEIGHT_ABSOLUTE_OFFSET",
    "PACKED_WEIGHT_BYTES",
    "PACKED_WEIGHT_SHA256",
    "PHONE_RECEIPT_SCHEMA",
    "PREREGISTRATION_SCHEMA",
    "SCALE_ABSOLUTE_OFFSET",
    "SCALE_BF16_RNE_AS_F32_SHA256",
    "SCALE_F32_BYTES",
    "SCALE_F32_SHA256",
    "SENTINEL_CASE_ID",
    "SENTINEL_INPUT_SHA256",
    "adjudicate_bf16_output",
    "bf16_rne_scales",
    "build_preregistration",
    "canonical_json",
    "decode_bf16",
    "frozen_thresholds",
    "hash_range",
    "normalize_opencl_contract",
    "off_s16_lattice_sentinel",
    "read_range",
    "read_regular",
    "resolve_relative",
    "runtime_environment",
    "sentinel_reference_output",
    "s16_input_to_bf16",
    "sha256_bytes",
    "sha256_path",
    "strict_json_decode",
    "strict_json_load",
    "validate_preregistration",
    "validate_regular",
    "validate_source_closure",
    "write_exclusive",
]
