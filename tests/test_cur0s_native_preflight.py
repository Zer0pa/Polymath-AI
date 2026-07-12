"""Host tests for the isolated CUR-0S libc-only native preflight."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import stat
import subprocess
import sys
import textwrap

import pytest

from polymath_ai.corpus.cur0s_commercial_sources import canonical_json_bytes


ROOT = Path(__file__).resolve().parents[1]
NATIVE_ROOT = ROOT / "scripts/termux/native"
SHA256_SOURCE = NATIVE_ROOT / "cur0s_sha256.c"
PREFLIGHT_SOURCE = NATIVE_ROOT / "cur0s_native_preflight.c"
TREE_CANONICALIZATION = (
    "sorted_relative_POSIX_paths_canonical_JSON_type_mode_"
    "regular_bytes_sha256_source_only_excluding_root_site_packages_"
    "all_pycache_and_pyc_reject_external_symlinks_root_excluded"
)
SECURITY_CEILING = (
    "observational_only_no_guarantee_against_a_concurrent_malicious_"
    "same_uid_between_checks"
)
RUN_ID = "20260712T120000Z_cur0s_commercial_sources_v1"
ACTION_PATH = "/data/data/com.termux/files/home/polymath_gemma4_e4b_frontier/" + RUN_ID
OUTPUT_PATH = ACTION_PATH + "/candidate_runs/candidate-001"
LAUNCH_ENVIRONMENT = {
    "ANDROID_ROOT": "/system",
    "CUR0S_NATIVE_ATTESTATION_FD": "4",
    "CUR0S_NATIVE_MANIFEST_FD": "5",
    "CUR0S_PREREGISTRATION_FD": "6",
    "HOME": "/data/data/com.termux/files/home",
    "LC_ALL": "C",
    "LD_PRELOAD": "/data/data/com.termux/files/usr/lib/libtermux-exec.so",
    "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
    "TERMUX_EXEC__PROC_SELF_EXE": "/data/data/com.termux/files/usr/bin/python",
}
LAUNCH_ENVIRONMENT_SHA256 = (
    "sha256:a6b03c74f6b9667c2c65e6eb1c72a396133263e3776124d1bc380fa4e3416883"
)
OUTER_ENVIRONMENT = {}
OUTER_ENVIRONMENT_SHA256 = (
    "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)


def _compiler() -> str:
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("a host C compiler is required")
    return compiler


@pytest.fixture(scope="session")
def native_preflight(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("cur0s-native-build") / "cur0s-native-preflight"
    command = [
        _compiler(),
        "-std=c17",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        "-fPIE",
        "-DCUR0S_NATIVE_PREFLIGHT_TESTING=1",
        "-I",
        str(NATIVE_ROOT),
        str(SHA256_SOURCE),
        str(PREFLIGHT_SOURCE),
        "-o",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output


@pytest.fixture(scope="session")
def descriptor_hygiene_harnesses(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path]:
    build_root = tmp_path_factory.mktemp("cur0s-descriptor-hygiene-build")
    harness_source = build_root / "descriptor-hygiene-harness.c"
    harness_source.write_text(
        textwrap.dedent(
            """
            #define CUR0S_NATIVE_PREFLIGHT_TESTING 1
            #define main cur0s_embedded_preflight_main
            #include "cur0s_native_preflight.c"
            #undef main

            int main(int argument_count, char **arguments) {
                char *empty_environment[] = {NULL};

                if (argument_count < 2) {
                    return 64;
                }
                error_code = NULL;
                if (mark_all_ambient_descriptors_close_on_exec() != 0) {
                    fprintf(stderr, "%s\\n", error_code);
                    return 70;
                }
                execve(arguments[1], &arguments[1], empty_environment);
                return 71;
            }
            """
        ),
        encoding="utf-8",
    )

    def compile_harness(name: str, descriptor_directory: str | None) -> Path:
        output = build_root / name
        command = [
            _compiler(),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-fPIE",
        ]
        if descriptor_directory is not None:
            command.append(
                f'-DCUR0S_AMBIENT_DESCRIPTOR_DIRECTORY="{descriptor_directory}"'
            )
        command.extend(
            (
                "-I",
                str(NATIVE_ROOT),
                str(SHA256_SOURCE),
                str(harness_source),
                "-o",
                str(output),
            )
        )
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output

    successful = compile_harness("descriptor-hygiene", None)
    failing = compile_harness(
        "descriptor-hygiene-forced-failure",
        "/cur0s-intentionally-absent-descriptor-directory",
    )
    return successful, failing


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _mode(information: os.stat_result) -> str:
    return f"{stat.S_IMODE(information.st_mode):04o}"


def _file_manifest_line(path: Path) -> str:
    information = path.stat(follow_symlinks=False)
    return "\t".join(
        (
            "FILE",
            str(path),
            _mode(information),
            str(information.st_uid),
            str(information.st_gid),
            str(information.st_nlink),
            str(information.st_size),
            _sha256(path.read_bytes()),
        )
    )


def _role_file_manifest_line(path: Path, role: str) -> str:
    line = _file_manifest_line(path) + f"\t{role}"
    return line + "\t0\t4096" if role == "native-self" else line


def _symlink_manifest_line(path: Path) -> str:
    information = path.stat(follow_symlinks=False)
    return "\t".join(
        (
            "SYMLINK",
            str(path),
            _mode(information),
            str(information.st_uid),
            str(information.st_gid),
            str(information.st_nlink),
            os.readlink(path),
        )
    )


def _execution_plan_line(python_argv0: Path) -> str:
    return "\t".join(
        (
            "EXEC_PLAN",
            RUN_ID,
            ACTION_PATH,
            OUTPUT_PATH,
            str(python_argv0),
            "-IBS",
            "-X",
            ACTION_PATH + "/python_pycache_forbidden",
            LAUNCH_ENVIRONMENT_SHA256,
            OUTER_ENVIRONMENT_SHA256,
            "3",
            "4",
            "5",
            "6",
        )
    )


def _runner_tree_identity(root: Path) -> tuple[int, int, str]:
    records: list[dict[str, object]] = []
    regular_bytes = 0

    def visit(directory: Path, prefix: str) -> None:
        nonlocal regular_bytes
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda entry: entry.name)
        for entry in ordered:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            information = entry.stat(follow_symlinks=False)
            mode = _mode(information)
            if stat.S_ISDIR(information.st_mode):
                records.append(
                    {
                        "relative_path": relative,
                        "type": "directory",
                        "mode": mode,
                    }
                )
                visit(Path(entry.path), relative)
            elif stat.S_ISLNK(information.st_mode):
                records.append(
                    {
                        "relative_path": relative,
                        "type": "symlink",
                        "mode": mode,
                        "target": os.readlink(entry.path),
                    }
                )
            elif stat.S_ISREG(information.st_mode) and information.st_nlink == 1:
                payload = Path(entry.path).read_bytes()
                regular_bytes += len(payload)
                records.append(
                    {
                        "relative_path": relative,
                        "type": "regular",
                        "mode": mode,
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
            else:
                raise AssertionError(f"unsafe synthetic fixture entry: {entry.path}")

    visit(root, "")
    records.sort(key=lambda item: item["relative_path"])
    root_digest = _sha256(canonical_json_bytes(records))
    return len(records), regular_bytes, root_digest


def _tree_manifest_line(root: Path) -> str:
    information = root.stat(follow_symlinks=False)
    entry_count, regular_bytes, digest = _runner_tree_identity(root)
    return "\t".join(
        (
            "STDLIB_TREE",
            str(root),
            _mode(information),
            str(information.st_uid),
            str(information.st_gid),
            str(information.st_nlink),
            str(entry_count),
            str(regular_bytes),
            digest,
            TREE_CANONICALIZATION,
        )
    )


def _write_manifest(path: Path, *lines: str) -> str:
    payload = (
        "CUR0S_NATIVE_PREFLIGHT_MANIFEST_V3\n" + "".join(f"{line}\n" for line in lines)
    ).encode("utf-8")
    path.write_bytes(payload)
    return _sha256(payload)


def _run(
    binary: Path,
    manifest: Path,
    manifest_digest: str,
    *,
    extra_arguments: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            str(binary),
            "--verify-only",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            manifest_digest,
            *extra_arguments,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _run_test_launch_plan(
    binary: Path,
    manifest: Path,
    manifest_digest: str,
    preregistration_digest: str,
    *,
    extra_arguments: tuple[str, ...] = (),
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            str(binary),
            "--test-launch-plan",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            manifest_digest,
            "--expected-preregistration-sha256",
            preregistration_digest,
            *extra_arguments,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
        env={} if environment is None else environment,
    )


def _build_launch_manifest(
    native_preflight: Path,
    root: Path,
    *,
    native_self_path: Path | None = None,
    include_roles: tuple[str, ...] = (
        "native-self",
        "python",
        "runner",
        "preregistration",
    ),
) -> tuple[Path, str, str, dict[str, Path]]:
    python = root / "python3.13"
    shutil.copyfile(native_preflight, python)
    python.chmod(0o700)
    python_argv0 = root / "python"
    python_argv0.symlink_to(python.name)
    runner = root / "run_cur0s_commercial_sources.py"
    runner.write_bytes(b"raise SystemExit('test plan must not execute')\n")
    runner.chmod(0o600)
    preregistration = root / "preregistration.json"
    preregistration.write_bytes(b'{"test_only":true}\n')
    preregistration.chmod(0o600)
    role_paths = {
        "native-self": native_self_path or native_preflight,
        "python": python,
        "runner": runner,
        "preregistration": preregistration,
    }
    lines = [_role_file_manifest_line(role_paths[role], role) for role in include_roles]
    lines.extend(
        (
            _symlink_manifest_line(python_argv0),
            _execution_plan_line(python_argv0),
        )
    )
    manifest = root / "launch-manifest.txt"
    manifest_digest = _write_manifest(manifest, *lines)
    manifest.chmod(0o600)
    return (
        manifest,
        manifest_digest,
        _sha256(preregistration.read_bytes()),
        {**role_paths, "python_argv0": python_argv0},
    )


def test_sha256_matches_exact_fips_vectors(tmp_path: Path) -> None:
    harness = tmp_path / "sha256-vectors.c"
    binary = tmp_path / "sha256-vectors"
    harness.write_text(
        textwrap.dedent(
            """
            #include "cur0s_sha256.h"
            #include <stdint.h>
            #include <stdio.h>
            #include <string.h>

            static void emit(const void *payload, size_t bytes, size_t split) {
                cur0s_sha256_context context;
                uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
                char hex[CUR0S_SHA256_HEX_BYTES + 1U];
                const uint8_t *cursor = (const uint8_t *)payload;
                cur0s_sha256_init(&context);
                while (bytes > 0U) {
                    size_t chunk = bytes < split ? bytes : split;
                    cur0s_sha256_update(&context, cursor, chunk);
                    cursor += chunk;
                    bytes -= chunk;
                }
                cur0s_sha256_final(&context, digest);
                cur0s_sha256_hex(digest, hex);
                puts(hex);
            }

            int main(void) {
                static const char long_vector[] =
                    "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
                char thousand_as[1000];
                cur0s_sha256_context context;
                uint8_t digest[CUR0S_SHA256_DIGEST_BYTES];
                char hex[CUR0S_SHA256_HEX_BYTES + 1U];

                emit("", 0U, 1U);
                emit("abc", 3U, 1U);
                emit(long_vector, strlen(long_vector), 7U);
                memset(thousand_as, 'a', sizeof(thousand_as));
                cur0s_sha256_init(&context);
                for (size_t index = 0; index < 1000U; ++index) {
                    cur0s_sha256_update(&context, thousand_as, sizeof(thousand_as));
                }
                cur0s_sha256_final(&context, digest);
                cur0s_sha256_hex(digest, hex);
                puts(hex);
                return 0;
            }
            """
        ),
        encoding="utf-8",
    )
    subprocess.run(
        (
            _compiler(),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-I",
            str(NATIVE_ROOT),
            str(SHA256_SOURCE),
            str(harness),
            "-o",
            str(binary),
        ),
        check=True,
        capture_output=True,
        text=True,
    )

    observed = subprocess.run(
        (str(binary),),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert observed == [
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
        "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0",
    ]


def test_verify_only_file_manifest_is_nofollow_and_write_free(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "authority.bin"
    artifact.write_bytes(b"immutable authority bytes\n")
    artifact.chmod(0o640)
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _file_manifest_line(artifact))
    initial = artifact.stat(follow_symlinks=False)
    initial_listing = sorted(path.name for path in tmp_path.iterdir())

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "schema_version": "cur0s_native_preflight_result_v1",
        "status": "verified",
        "mode": "verify_only",
        "manifest_sha256": manifest_digest,
        "entries_verified": 1,
        "passes_completed": 2,
        "persistent_writes": False,
        "security_ceiling": SECURITY_CEILING,
    }
    final = artifact.stat(follow_symlinks=False)
    assert (
        final.st_ino,
        final.st_mode,
        final.st_size,
        final.st_mtime_ns,
        final.st_ctime_ns,
    ) == (
        initial.st_ino,
        initial.st_mode,
        initial.st_size,
        initial.st_mtime_ns,
        initial.st_ctime_ns,
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == initial_listing


def test_stdlib_tree_root_matches_runner_canonicalization(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    tree = tmp_path / "stdlib"
    nested = tree / "pkg Ω"
    nested.mkdir(parents=True)
    tree.chmod(0o750)
    nested.chmod(0o710)
    (tree / "plain.py").write_bytes(b"print('plain')\n")
    (tree / "plain.py").chmod(0o640)
    unusual = nested / 'quote"name\nmodule.py'
    unusual.write_bytes("π = 3.14159\n".encode())
    unusual.chmod(0o600)
    os.symlink('../missing "target"\nΩ', nested / "literal-link")
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _tree_manifest_line(tree))

    forward = _run(native_preflight, manifest, manifest_digest)
    reverse = _run(native_preflight, manifest, manifest_digest)

    assert forward.returncode == 0, forward.stderr
    assert reverse.returncode == 0, reverse.stderr
    assert json.loads(forward.stdout)["passes_completed"] == 2
    assert forward.stdout == reverse.stdout


def test_empty_stdlib_tree_matches_runner_empty_list_root(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    tree = tmp_path / "empty-stdlib"
    tree.mkdir()
    tree.chmod(0o700)
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _tree_manifest_line(tree))

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["entries_verified"] == 1


@pytest.mark.parametrize("link_location", ["leaf", "ancestor"])
def test_secure_open_rejects_symlink_path_components(
    native_preflight: Path,
    tmp_path: Path,
    link_location: str,
) -> None:
    actual_directory = tmp_path / "actual"
    actual_directory.mkdir()
    actual = actual_directory / "authority.bin"
    actual.write_bytes(b"bound bytes")
    if link_location == "leaf":
        supplied = tmp_path / "authority-link"
        supplied.symlink_to(actual)
    else:
        linked_directory = tmp_path / "linked-directory"
        linked_directory.symlink_to(actual_directory, target_is_directory=True)
        supplied = linked_directory / actual.name
    information = actual.stat()
    line = "\t".join(
        (
            "FILE",
            str(supplied),
            _mode(information),
            str(information.st_uid),
            str(information.st_gid),
            str(information.st_nlink),
            str(information.st_size),
            _sha256(actual.read_bytes()),
        )
    )
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, line)

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 1
    rejection = json.loads(completed.stderr)
    assert rejection["status"] == "rejected"
    assert rejection["error"] == "secure_path_component_open_failed"
    assert rejection["security_ceiling"] == SECURITY_CEILING


def test_file_manifest_rejects_hard_link_aliases(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "authority.bin"
    alias = tmp_path / "authority-alias.bin"
    artifact.write_bytes(b"multiply reachable bytes")
    os.link(artifact, alias)
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _file_manifest_line(artifact))

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 1
    assert json.loads(completed.stderr)["error"] == "file_stat_mismatch"


def test_manifest_itself_is_sha_bound_and_nofollow(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "authority.bin"
    artifact.write_bytes(b"bound bytes")
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _file_manifest_line(artifact))

    mismatched = _run(
        native_preflight,
        manifest,
        "sha256:" + ("0" * 64),
    )
    assert mismatched.returncode == 1
    assert json.loads(mismatched.stderr)["error"] == "manifest_sha256_mismatch"

    manifest_link = tmp_path / "manifest-link"
    manifest_link.symlink_to(manifest)
    linked = _run(native_preflight, manifest_link, manifest_digest)
    assert linked.returncode == 1
    assert json.loads(linked.stderr)["error"] == "secure_path_component_open_failed"


def test_second_pass_detects_identical_byte_path_replacement(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "authority.bin"
    payload = b"same digest and size, different inode\n"
    artifact.write_bytes(payload)
    artifact.chmod(0o640)
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _file_manifest_line(artifact))
    signal_read, signal_write = os.pipe()
    resume_read, resume_write = os.pipe()
    environment = {
        **os.environ,
        "CUR0S_PREFLIGHT_TEST_SIGNAL_FD": str(signal_write),
        "CUR0S_PREFLIGHT_TEST_RESUME_FD": str(resume_read),
    }
    process = subprocess.Popen(
        (
            str(native_preflight),
            "--verify-only",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            manifest_digest,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        pass_fds=(signal_write, resume_read),
    )
    os.close(signal_write)
    os.close(resume_read)
    try:
        readable, _, _ = select.select((signal_read,), (), (), 10)
        assert readable, "native preflight did not reach the between-pass barrier"
        assert os.read(signal_read, 1) == b"1"
        backup = tmp_path / "authority-first-pass.bin"
        artifact.rename(backup)
        artifact.write_bytes(payload)
        artifact.chmod(0o640)
        os.write(resume_write, b"1")
        stdout, stderr = process.communicate(timeout=10)
    finally:
        os.close(signal_read)
        os.close(resume_write)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert process.returncode == 1, stdout
    rejection = json.loads(stderr)
    assert rejection["error"] == "entry_changed_between_passes"
    assert rejection["persistent_writes"] is False


def test_verify_only_is_mandatory(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "authority.bin"
    artifact.write_bytes(b"bound bytes")
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _file_manifest_line(artifact))

    completed = subprocess.run(
        (
            str(native_preflight),
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            manifest_digest,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 2
    rejection = json.loads(completed.stderr)
    assert rejection["error"] == "usage_invalid"
    assert rejection["mode"] == "verify_only"


def test_manifest_symlink_record_binds_literal_entry_without_following(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    target = tmp_path / "resolved.bin"
    target.write_bytes(b"the link target must never be opened")
    link = tmp_path / "authority-link"
    link.symlink_to(target.name)
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _symlink_manifest_line(link))

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["entries_verified"] == 1
    assert result["passes_completed"] == 2


def test_manifest_symlink_record_rejects_wrong_literal_target(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    link = tmp_path / "authority-link"
    link.symlink_to("actual-target")
    fields = _symlink_manifest_line(link).split("\t")
    fields[-1] = "forged-target"
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, "\t".join(fields))

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 1
    assert json.loads(completed.stderr)["error"] == (
        "symlink_identity_or_target_mismatch"
    )


def test_symlink_second_pass_detects_same_target_inode_rebind(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    link = tmp_path / "authority-link"
    link.symlink_to("stable-literal-target")
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _symlink_manifest_line(link))
    signal_read, signal_write = os.pipe()
    resume_read, resume_write = os.pipe()
    process = subprocess.Popen(
        (
            str(native_preflight),
            "--verify-only",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            manifest_digest,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "CUR0S_PREFLIGHT_TEST_SIGNAL_FD": str(signal_write),
            "CUR0S_PREFLIGHT_TEST_RESUME_FD": str(resume_read),
        },
        pass_fds=(signal_write, resume_read),
    )
    os.close(signal_write)
    os.close(resume_read)
    try:
        readable, _, _ = select.select((signal_read,), (), (), 10)
        assert readable
        assert os.read(signal_read, 1) == b"1"
        link.unlink()
        link.symlink_to("stable-literal-target")
        os.write(resume_write, b"1")
        stdout, stderr = process.communicate(timeout=10)
    finally:
        os.close(signal_read)
        os.close(resume_write)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert process.returncode == 1, stdout
    assert json.loads(stderr)["error"] == "entry_changed_between_passes"


def test_manifest_symlink_rejects_symlinked_ancestor(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = actual / "leaf"
    link.symlink_to("literal-target")
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    fields = _symlink_manifest_line(link).split("\t")
    fields[1] = str(alias / link.name)
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, "\t".join(fields))

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 1
    assert json.loads(completed.stderr)["error"] == (
        "secure_path_component_open_failed"
    )


def test_tree_depth_cap_rejects_adversarial_nesting(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    tree = tmp_path / "stdlib"
    tree.mkdir()
    cursor = tree
    for _ in range(129):
        cursor /= "d"
        cursor.mkdir()
    manifest = tmp_path / "manifest.txt"
    manifest_digest = _write_manifest(manifest, _tree_manifest_line(tree))

    completed = _run(native_preflight, manifest, manifest_digest)

    assert completed.returncode == 1
    assert json.loads(completed.stderr)["error"] == "tree_depth_limit_exceeded"


def test_ambient_high_descriptor_is_cloexec_before_python_child(
    descriptor_hygiene_harnesses: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    successful_harness, _ = descriptor_hygiene_harnesses
    child = tmp_path / "inspect-descriptor.py"
    result = tmp_path / "descriptor-result.txt"
    child.write_text(
        textwrap.dedent(
            """
            import errno
            import os
            import sys

            descriptor = int(sys.argv[1])
            result = sys.argv[2]
            try:
                os.fstat(descriptor)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise
                observed = "closed"
            else:
                observed = "survived"
            with open(result, "w", encoding="ascii") as handle:
                handle.write(observed)
            raise SystemExit(0 if observed == "closed" else 1)
            """
        ),
        encoding="utf-8",
    )
    source_descriptor = os.open(os.devnull, os.O_RDONLY)
    inherited_descriptor = fcntl.fcntl(source_descriptor, fcntl.F_DUPFD, 137)
    os.set_inheritable(inherited_descriptor, True)
    try:
        completed = subprocess.run(
            (
                str(successful_harness),
                sys.executable,
                "-I",
                "-B",
                "-S",
                str(child),
                str(inherited_descriptor),
                str(result),
            ),
            check=False,
            capture_output=True,
            text=True,
            env={},
            pass_fds=(inherited_descriptor,),
            timeout=20,
        )
    finally:
        os.close(inherited_descriptor)
        os.close(source_descriptor)

    assert completed.returncode == 0, completed.stderr
    assert result.read_text(encoding="ascii") == "closed"


def test_descriptor_hygiene_failure_cannot_launch_child(
    descriptor_hygiene_harnesses: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    _, failing_harness = descriptor_hygiene_harnesses
    marker = tmp_path / "child-launched"
    child = tmp_path / "write-launch-marker.py"
    child.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[1]).write_text('launched', encoding='ascii')\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        (
            str(failing_harness),
            sys.executable,
            "-I",
            "-B",
            "-S",
            str(child),
            str(marker),
        ),
        check=False,
        capture_output=True,
        text=True,
        env={},
        timeout=20,
    )

    assert completed.returncode == 70
    assert completed.stderr == "launch_ambient_descriptor_directory_open_failed\n"
    assert not marker.exists()


@pytest.mark.parametrize(
    "dirty_environment",
    (
        {"UNBOUND_OUTER_VALUE": "1"},
        {"LD_UNBOUND_SENTINEL": "must-not-reach-native-launch"},
    ),
)
def test_launch_rejects_nonempty_outer_environment_before_authority_open(
    native_preflight: Path,
    tmp_path: Path,
    dirty_environment: dict[str, str],
) -> None:
    absent_manifest = tmp_path / "must-not-be-opened.manifest"

    completed = _run_test_launch_plan(
        native_preflight,
        absent_manifest,
        "sha256:" + ("0" * 64),
        "sha256:" + ("0" * 64),
        environment=dirty_environment,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stderr)["error"] == "outer_environment_not_empty"
    assert not absent_manifest.exists()


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    (
        ("missing", "manifest_entry_schema_invalid"),
        ("forged", "manifest_execution_plan_invalid"),
    ),
)
def test_launch_rejects_missing_or_forged_outer_environment_binding(
    native_preflight: Path,
    tmp_path: Path,
    mutation: str,
    expected_error: str,
) -> None:
    manifest, _, preregistration_digest, _ = _build_launch_manifest(
        native_preflight,
        tmp_path,
    )
    lines = manifest.read_text(encoding="utf-8").splitlines()
    plan_index = next(
        index for index, line in enumerate(lines) if line.startswith("EXEC_PLAN\t")
    )
    fields = lines[plan_index].split("\t")
    if mutation == "missing":
        del fields[7]
    else:
        fields[7] = "sha256:" + ("0" * 64)
    lines[plan_index] = "\t".join(fields)
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    manifest.write_bytes(payload)

    completed = _run_test_launch_plan(
        native_preflight,
        manifest,
        _sha256(payload),
        preregistration_digest,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stderr)["error"] == expected_error


def test_test_launch_plan_binds_roles_self_argv_environment_and_attestation(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    assert _sha256(canonical_json_bytes(LAUNCH_ENVIRONMENT)) == (
        LAUNCH_ENVIRONMENT_SHA256
    )
    assert _sha256(canonical_json_bytes(OUTER_ENVIRONMENT)) == (
        OUTER_ENVIRONMENT_SHA256
    )
    manifest, manifest_digest, preregistration_digest, paths = _build_launch_manifest(
        native_preflight, tmp_path
    )
    initial_listing = sorted(path.name for path in tmp_path.iterdir())

    completed = _run_test_launch_plan(
        native_preflight,
        manifest,
        manifest_digest,
        preregistration_digest,
    )

    assert completed.returncode == 0, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan["schema_version"] == "cur0s_native_launch_plan_v1"
    assert plan["status"] == "verified"
    assert plan["mode"] == "test_launch_plan"
    assert plan["production_launch_performed"] is False
    assert plan["environment"] == LAUNCH_ENVIRONMENT
    assert plan["fixed_fds"] == {
        "manifest": 5,
        "native_attestation": 4,
        "preregistration": 6,
        "python_exec_cloexec": 7,
        "runner": 3,
    }
    assert plan["argv"] == [
        str(paths["python_argv0"]),
        "-IBS",
        "-X",
        "pycache_prefix=" + ACTION_PATH + "/python_pycache_forbidden",
        "/proc/self/fd/3",
        "--preregistration",
        str(paths["preregistration"]),
        "--expected-preregistration-sha256",
        preregistration_digest,
        "--output-dir",
        OUTPUT_PATH,
    ]
    assert plan["memfd_required_seals"] == [
        "F_SEAL_GROW",
        "F_SEAL_SEAL",
        "F_SEAL_SHRINK",
        "F_SEAL_WRITE",
    ]
    attestation = plan["native_attestation"]
    native_maps = {
        "capture_timing": "first_action_in_main_before_argument_parsing",
        "executable_mapping_policy": (
            "exact_nine_record_phone_native_runtime_closure_only"
        ),
        "production_policy_enforced": False,
        "records": [],
        "schema_version": "cur0s_native_earliest_main_maps_v1",
        "unexpected_executable_mappings_absent": False,
        "vvar": {"nonexecutable": None, "present": False},
    }
    assert attestation == {
        "entries_verified": 5,
        "fixed_fds": plan["fixed_fds"],
        "helper_dependency_swap_safety_claimed": False,
        "manifest_sha256": manifest_digest,
        "mode": "launch",
        "native_maps": native_maps,
        "native_maps_root_sha256": _sha256(canonical_json_bytes(native_maps)),
        "outer_env_observed": True,
        "outer_environment_sha256": OUTER_ENVIRONMENT_SHA256,
        "passes_completed": 2,
        "persistent_writes": False,
        "pid": attestation["pid"],
        "python_pycache_prefix": ACTION_PATH + "/python_pycache_forbidden",
        "python_pycache_prefix_absent": True,
        "roles": {
            role: {
                "bytes": paths[role].stat(follow_symlinks=False).st_size,
                "path": str(paths[role]),
                "sha256": _sha256(paths[role].read_bytes()),
            }
            for role in (
                "native-self",
                "preregistration",
                "python",
                "runner",
            )
        },
        "run_id": RUN_ID,
        "schema_version": "cur0s_native_launch_attestation_v2",
        "security_ceiling": SECURITY_CEILING,
        "status": "verified",
    }
    assert plan["native_attestation_sha256"] == _sha256(
        canonical_json_bytes(attestation)
    )
    assert sorted(path.name for path in tmp_path.iterdir()) == initial_listing
    assert not Path(OUTPUT_PATH).exists()


def test_launch_plan_rejects_missing_role_and_preregistration_digest_mismatch(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    manifest, manifest_digest, preregistration_digest, _ = _build_launch_manifest(
        native_preflight,
        missing_root,
        include_roles=("native-self", "python", "preregistration"),
    )
    missing = _run_test_launch_plan(
        native_preflight,
        manifest,
        manifest_digest,
        preregistration_digest,
    )
    assert missing.returncode == 1
    assert json.loads(missing.stderr)["error"] == "launch_required_file_role_missing"

    mismatch_root = tmp_path / "mismatch"
    mismatch_root.mkdir()
    manifest, manifest_digest, _, _ = _build_launch_manifest(
        native_preflight,
        mismatch_root,
    )
    mismatch = _run_test_launch_plan(
        native_preflight,
        manifest,
        manifest_digest,
        "sha256:" + ("0" * 64),
    )
    assert mismatch.returncode == 1
    assert json.loads(mismatch.stderr)["error"] == (
        "launch_expected_preregistration_sha256_mismatch"
    )


def test_launch_plan_rejects_forged_native_self_and_extra_cli_argument(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    forged_self = tmp_path / "forged-native-self"
    shutil.copyfile(native_preflight, forged_self)
    forged_self.chmod(0o700)
    root = tmp_path / "launch"
    root.mkdir()
    manifest, manifest_digest, preregistration_digest, _ = _build_launch_manifest(
        native_preflight,
        root,
        native_self_path=forged_self,
    )

    forged = _run_test_launch_plan(
        native_preflight,
        manifest,
        manifest_digest,
        preregistration_digest,
    )
    assert forged.returncode == 1
    assert json.loads(forged.stderr)["error"] == (
        "test_launch_native_self_invocation_path_mismatch"
    )

    extra = _run_test_launch_plan(
        native_preflight,
        manifest,
        manifest_digest,
        preregistration_digest,
        extra_arguments=("--unbound-runner-argument",),
    )
    assert extra.returncode == 2
    assert json.loads(extra.stderr)["error"] == "usage_invalid"


def test_production_launch_rejects_non_android_and_test_hooks_compile_out(
    native_preflight: Path,
    tmp_path: Path,
) -> None:
    root = tmp_path / "launch"
    root.mkdir()
    manifest, manifest_digest, preregistration_digest, _ = _build_launch_manifest(
        native_preflight,
        root,
    )
    rejected = subprocess.run(
        (
            str(native_preflight),
            "--launch",
            "--manifest",
            str(manifest),
            "--manifest-sha256",
            manifest_digest,
            "--expected-preregistration-sha256",
            preregistration_digest,
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stderr)["error"] == "launch_requires_android_api30"

    production = tmp_path / "cur0s-native-preflight-production"
    subprocess.run(
        (
            _compiler(),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-fPIE",
            "-DCUR0S_NATIVE_PREFLIGHT_TESTING=0",
            "-I",
            str(NATIVE_ROOT),
            str(SHA256_SOURCE),
            str(PREFLIGHT_SOURCE),
            "-o",
            str(production),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    payload = production.read_bytes()
    assert b"--test-launch-plan" not in payload
    assert b"CUR0S_PREFLIGHT_TEST_SIGNAL_FD" not in payload
    assert b"CUR0S_PREFLIGHT_TEST_RESUME_FD" not in payload


def test_earliest_main_maps_gate_rejects_length_extra_and_cardinality_mutations(
    tmp_path: Path,
) -> None:
    maps_path = tmp_path / "synthetic-proc-maps"
    binary = tmp_path / "maps-gate"
    subprocess.run(
        (
            _compiler(),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-fPIE",
            "-DCUR0S_NATIVE_PREFLIGHT_TESTING=0",
            f'-DCUR0S_NATIVE_MAPS_PATH="{maps_path}"',
            "-I",
            str(NATIVE_ROOT),
            str(SHA256_SOURCE),
            str(PREFLIGHT_SOURCE),
            "-o",
            str(binary),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    specifications = [
        (str(binary), 0x4000, 0x2000, 1, 11, "r-xp"),
        ("/apex/com.android.runtime/bin/linker64", 0x4C000, 0x116000, 2, 12, "r-xp"),
        (
            "/apex/com.android.runtime/lib64/bionic/libc.so",
            0x48000,
            0x8F000,
            3,
            13,
            "r-xp",
        ),
        (
            "/apex/com.android.runtime/lib64/bionic/libdl.so",
            0x4000,
            0x1000,
            4,
            14,
            "r-xp",
        ),
        (
            "/apex/com.android.runtime/lib64/bionic/libm.so",
            0x14000,
            0x24000,
            5,
            15,
            "r-xp",
        ),
        ("/system/lib64/libc++.so", 0x84000, 0x7B000, 6, 16, "r-xp"),
        ("/system/lib64/libnetd_client.so", 0x4000, 0x4000, 7, 17, "r-xp"),
        ("[vvar]", 0, 0x2000, 0, 0, "r--p"),
        ("[vdso]", 0, 0x1000, 0, 0, "r-xp"),
    ]

    def payload(values) -> bytes:
        lines: list[str] = []
        address = 0x7000000000
        for path, offset, mapped, device, inode, permissions in values:
            lines.append(
                f"{address:x}-{address + mapped:x} {permissions} {offset:08x} "
                f"{device:02x}:{device:02x} {inode} {path}\n"
            )
            address += mapped + 0x10000
        return "".join(lines).encode("ascii")

    def rejection(values) -> str:
        maps_path.write_bytes(payload(values))
        completed = subprocess.run(
            (str(binary), "--invalid"),
            check=False,
            capture_output=True,
            text=True,
            env={},
        )
        return json.loads(completed.stderr)["error"]

    assert rejection(specifications) == "usage_invalid"
    wrong_length = list(specifications)
    wrong_length[1] = (
        wrong_length[1][0],
        wrong_length[1][1],
        wrong_length[1][2] + 0x1000,
        *wrong_length[1][3:],
    )
    assert rejection(wrong_length) == "earliest_native_maps_mapping_shape_mismatch"
    extra = [
        *specifications,
        ("/data/local/tmp/injected.so", 0, 0x1000, 8, 18, "r-xp"),
    ]
    assert rejection(extra) == "earliest_native_maps_unexpected_executable_mapping"
    assert rejection(specifications[:-1]) == (
        "earliest_native_maps_required_mapping_missing"
    )
    assert rejection([*specifications, specifications[-1]]) == (
        "earliest_native_maps_required_mapping_missing"
    )


def test_production_manifest_binding_requires_exact_native_self_pt_load_geometry(
    tmp_path: Path,
) -> None:
    harness_source = tmp_path / "native-map-binding-harness.c"
    harness_source.write_text(
        textwrap.dedent(
            """
            #define CUR0S_NATIVE_PREFLIGHT_TESTING 0
            #define main cur0s_embedded_preflight_main
            #include "cur0s_native_preflight.c"
            #undef main

            int main(int argument_count, char **arguments) {
                manifest_entry entry;
                manifest expected;
                observation observed;
                native_map_snapshot snapshot;
                native_map_record *record;
                int status;

                if (argument_count != 2) {
                    return 64;
                }
                memset(&entry, 0, sizeof(entry));
                memset(&expected, 0, sizeof(expected));
                memset(&observed, 0, sizeof(observed));
                memset(&snapshot, 0, sizeof(snapshot));
                entry.type = ENTRY_FILE;
                entry.path = "/native";
                entry.role = "native-self";
                entry.bytes = 0x4000U;
                entry.executable_map_geometry_present = 1;
                entry.executable_map_offset = 0x1000U;
                entry.executable_map_mapped_bytes = 0x2000U;
                expected.entries = &entry;
                expected.count = 1U;
                observed.identity.device = 0;
                observed.identity.inode = 3;
                observed.bytes = entry.bytes;
                snapshot.production_policy_enforced = 1;
                snapshot.count = 1U;
                record = &snapshot.records[0];
                record->device_major = 0U;
                record->device_minor = 0U;
                record->inode = 3U;
                record->offset = entry.executable_map_offset;
                record->mapped_bytes = entry.executable_map_mapped_bytes;
                strcpy(record->path, entry.path);
                strcpy(record->runtime_role, entry.role);

                if (strcmp(arguments[1], "wrong-offset") == 0) {
                    record->offset += 0x1000U;
                } else if (strcmp(arguments[1], "wrong-length") == 0) {
                    record->mapped_bytes += 0x1000U;
                } else if (strcmp(arguments[1], "missing-geometry") == 0) {
                    entry.executable_map_geometry_present = 0;
                } else if (strcmp(arguments[1], "exact") != 0) {
                    return 64;
                }
                error_code = NULL;
                status = bind_earliest_native_maps_to_manifest(
                    &snapshot,
                    &expected,
                    &observed
                );
                if (status == 0) {
                    puts("accepted");
                    return 0;
                }
                puts(error_code == NULL ? "missing_error" : error_code);
                return 1;
            }
            """
        ),
        encoding="utf-8",
    )
    binary = tmp_path / "native-map-binding-harness"
    subprocess.run(
        (
            _compiler(),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-fPIE",
            "-I",
            str(NATIVE_ROOT),
            str(SHA256_SOURCE),
            str(harness_source),
            "-o",
            str(binary),
        ),
        check=True,
        capture_output=True,
        text=True,
    )

    exact = subprocess.run(
        (str(binary), "exact"),
        check=False,
        capture_output=True,
        text=True,
    )
    assert exact.returncode == 0
    assert exact.stdout == "accepted\n"
    for mutation in ("wrong-offset", "wrong-length", "missing-geometry"):
        rejected = subprocess.run(
            (str(binary), mutation),
            check=False,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode == 1
        assert rejected.stdout == "earliest_native_maps_self_geometry_mismatch\n"


def test_earliest_maps_capture_is_first_executable_statement_in_main() -> None:
    source = PREFLIGHT_SOURCE.read_text(encoding="utf-8")
    main = source.split("int main(int argument_count, char **arguments) {", 1)[1]
    capture = main.index("maps_capture_status = capture_earliest_native_maps(")

    assert capture < main.index("memset(&config")
    assert capture < main.index("parse_arguments(argument_count")
    assert capture < main.index("observe_empty_outer_environment(&config)")


def test_android_launch_uses_kernel_execveat_and_execute_only_ancestor_traversal() -> (
    None
):
    source = PREFLIGHT_SOURCE.read_text(encoding="utf-8")

    assert "#include <sys/syscall.h>" in source
    assert "syscall(\n        __NR_execveat," in source
    assert "cur0s_platform_execveat(\n        PYTHON_EXEC_DESCRIPTOR," in source
    assert "\n    execveat(\n" not in source
    assert "return O_PATH | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW;" in source
    assert 'current_fd = open("/", ancestor_directory_open_flags());' in source
