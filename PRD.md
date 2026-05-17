# Active PRD

The active Polymath-AI route has pivoted.

Read this authority PRD:

`docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`

The old Qwen/ELO/mobile-fine-tuning framing is deprecated for this lane.

Current governing objective:

```text
End-to-end Gemma 4 native training on REDMAGIC SM8750:
HF raw text stream -> phone CPU tokenization -> phone UFS packed cache
-> phone Adreno / Hexagon / CPU training runtime
-> validated checkpoint or adapter artifact.
```

The passed Gemma 4 E4B layer 0 OpenCL phone gate is a regression floor, not a
terminal success narrative.
