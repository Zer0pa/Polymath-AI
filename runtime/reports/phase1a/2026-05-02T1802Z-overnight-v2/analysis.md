# v2 overnight run analysis

Total events: 254
Inference batches: 251
Start: 2026-05-02T11:51:28Z
End:   2026-05-02T18:07:20Z
Duration: 6.26 hours (22552 s)

## Halt events
  2026-05-02T18:07:19Z  stop_signal_received  payload={'reason': 'operator_touch_STOP', 'iter': 252}
  2026-05-02T18:07:20Z  phase1a_overnight_end  payload={'final_iter': 252}

## Per-scope batches
  qwen_block                      batches=226  total inferences=22600
  qwen_frozen_subgraph            batches=25  total inferences=250

## Success rate
  rc=0 count:       251 / 251
  out_size=98304:   251 / 251
  Other rcs: []

## Per-inference latency (ms)
  qwen_block: n=226, min=8, p5=9, p50=19, p95=22, p99=23, max=25, mean=16.8
  qwen_frozen_subgraph: n=25, min=251, p5=252, p50=576, p95=811, p99=817, max=817, mean=600.4

## Wall-ms per batch (whole-batch wall clock)
  qwen_block: n=226, min=867, p50=1908, p95=2241, max=2545, mean=1729
  qwen_frozen_subgraph: n=25, min=2513, p50=5764, p95=8110, max=8173, mean=6008

## Battery + thermal trajectory
  iter_idx  ts                       level%  bat_dC  cpu0_dC  ac_powered
         0  2026-05-02T11:51:28Z     72%   24.0°C   58.3°C  true
        30  2026-05-02T13:03:15Z     85%   22.0°C   52.1°C  true
        60  2026-05-02T13:35:10Z     85%   30.0°C   40.1°C  true
        90  2026-05-02T14:07:17Z     85%   28.0°C   36.6°C  true
       120  2026-05-02T14:39:07Z     79%   29.0°C   35.9°C  false
       150  2026-05-02T15:16:46Z     76%   29.0°C   35.5°C  false
       180  2026-05-02T15:53:00Z     73%   25.0°C   30.1°C  false
       210  2026-05-02T16:31:22Z     72%   23.0°C   28.1°C  false
       240  2026-05-02T17:03:54Z     71%   22.0°C   28.1°C  false
       253  2026-05-02T18:07:20Z     73%   28.0°C   58.7°C  true


Wrote /Users/zer0palab/Polymath-AI/runtime/reports/phase1a/2026-05-02T1802Z-overnight-v2/summary.json
{
