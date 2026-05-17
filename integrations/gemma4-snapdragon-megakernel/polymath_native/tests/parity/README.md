# Parity Tests

Host parity is driven by:

```bash
python3.11 polymath_native/tools/run_kernel_tests.py --build-dir build/native
```

REDMAGIC parity should reuse the same golden JSON and emit the same telemetry schema.
