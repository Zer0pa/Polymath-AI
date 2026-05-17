# REDMAGIC Vulkan/OpenCL Capability Probes

These scripts support Sub-agent C scouting for the Gemma 4 E4B forward gate. They
only establish backend feasibility; they do not satisfy the sovereign gate.

## Shell-Only Probe

Run after selecting the REDMAGIC serial:

```bash
export ADB=adb
export SERIAL=FY25013101C8
export OUT_DIR=runtime/probes/redmagic_gpu/$(date -u +%Y%m%dT%H%M%SZ)
bash gemma4_megakernel/android/adb/probe_gpu_shell.sh
```

Expected pass-shaped evidence:

- `adb_devices.txt` lists the selected serial as `device`, not `offline` or
  `unauthorized`.
- `device_identity.txt` matches the REDMAGIC target: `nubia`, `NX789J`,
  `SM8750`, `qcom`, `arm64-v8a`, Android `15`.
- `gpu_package_features.txt` includes Vulkan declarations such as
  `android.hardware.vulkan.version`, `android.hardware.vulkan.level`,
  `android.hardware.vulkan.compute`, or `android.hardware.vulkan.deqp.level`.
- `vulkan_vkjson.txt` contains JSON with a `devices` array. Each useful device
  has `properties.deviceName`, `properties.vendorID`,
  `properties.deviceID`, `properties.deviceType`, and
  `properties.apiVersion`.
- `gpu_libraries.txt` shows Vulkan loader/driver signals and may show
  `libOpenCL.so`. OpenCL is blocked until a native `clGetPlatformIDs` probe
  succeeds.

## Native Probe Runner

Use this only after a minimal arm64 Android probe binary exists. The binary must
query capabilities and exit; it must not allocate stress buffers, benchmark, or
change process/global graphics settings.

```bash
export ADB=adb
export SERIAL=FY25013101C8
export NATIVE_PROBE_BIN=/abs/path/to/gpu_capability_probe
export OUT_DIR=runtime/probes/redmagic_gpu_native/$(date -u +%Y%m%dT%H%M%SZ)
bash gemma4_megakernel/android/adb/run_native_gpu_probe.sh
```

Expected native Vulkan output:

- At least one physical device.
- At least one queue family with `VK_QUEUE_COMPUTE_BIT`.
- Device limits include `maxComputeSharedMemorySize`,
  `maxComputeWorkGroupInvocations`, `maxComputeWorkGroupSize`,
  `maxStorageBufferRange`, and `storageBufferOffsetAlignment`.
- Device extensions list is captured exactly.

Expected native OpenCL output:

- `dlopen("libOpenCL.so")` or an explicit searched vendor path succeeds.
- `clGetPlatformIDs` returns at least one platform.
- `clGetDeviceIDs(..., CL_DEVICE_TYPE_GPU, ...)` returns at least one GPU.
- Device info includes `CL_DEVICE_NAME`, `CL_DEVICE_VENDOR`,
  `CL_DEVICE_VERSION`, `CL_DRIVER_VERSION`, `CL_DEVICE_OPENCL_C_VERSION`,
  `CL_DEVICE_EXTENSIONS`, `CL_DEVICE_GLOBAL_MEM_SIZE`,
  `CL_DEVICE_LOCAL_MEM_SIZE`, and `CL_DEVICE_MAX_WORK_GROUP_SIZE`.
- `cl_khr_fp16` presence is recorded; absence does not block FP32 probing but
  blocks FP16-weight assumptions.

## Blocker Handling

- `adb: command not found`: set `ADB` to the platform-tools `adb` path.
- `unauthorized`: accept the phone trust prompt, then rerun only enumeration.
- `offline`: reconnect USB and rerun enumeration; do not restart phone services
  unless the orchestrator explicitly approves.
- Multiple devices: set `SERIAL`; do not run probes against the default target.
- `cmd gpu vkjson` missing or non-JSON: keep the transcript and require the
  native Vulkan probe before any Vulkan backend decision.
- No Vulkan feature declarations: treat Vulkan as blocked until native Vulkan
  enumeration disproves the shell evidence.
- No visible `libOpenCL.so`: treat OpenCL as blocked unless a native loader
  probe finds a usable vendor path.
- OpenCL `dlopen` fails due linker namespace or permission policy: record the
  error and switch to Vulkan first, or plan an APK-based OpenCL probe with
  declared native-library access.
- Native probe crashes or hangs: keep stdout/stderr/exit status, do not retry in
  loops, and reduce the probe to one backend at a time.

Commands intentionally excluded from this packet:

- `cmd thermalservice override-status ...`
- `setprop ...`
- `settings put ...`
- `am force-stop ...`
- root, remount, package disable/enable, or deleting phone files
