# Blockers

## Resolved Boundary Blocker For G3

ADB transport to the REDMAGIC disappeared after the initial successful probe.

Initial successful evidence:

- `adb devices -l` listed `FY25013101C8 device usb:0-1 product:NX789J-EEA model:NX789J device:NX789J`.
- `adb -s FY25013101C8 shell` returned model `NX789J`, SoC `SM8750`,
  manufacturer `nubia`, Android `15`, and showed
  `/data/local/tmp/polymath_gemma4_gate` with `gemma4_layer_runner`,
  `layer_pack`, and `outputs_opencl`.

Failure evidence:

- Non-destructive G1 replay later returned `adb: device 'FY25013101C8' not found`.
- `adb kill-server`, `adb start-server`, `adb reconnect`, and repeated
  `adb devices -l` showed no devices.
- `system_profiler SPUSBDataType` and `ioreg -p IOUSB` showed no matching
  REDMAGIC/NX789J/Qualcomm/Android device.

Resolution:

- The operator reconnected the device.
- ADB rediscovered `FY25013101C8`.
- G1 live replay passed with output sha256
  `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`.
- G3 subsequently passed in
  `runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/`.

No active G2 blocker remains.
