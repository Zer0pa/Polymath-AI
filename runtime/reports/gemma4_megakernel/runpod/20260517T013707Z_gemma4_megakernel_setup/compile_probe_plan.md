# Compile Probe Plan - Gemma 4 Snapdragon Megakernel Setup

Status: NOT_EXECUTED

## Scope

First compile candidate is a synthetic tiny RMSNorm + matmul graph shaped to match the Gemma 4 static-executor backend harness. This is a toolchain proof and not a model-training claim.

## Target Model Or Graph

- Candidate 1: synthetic RMSNorm/matmul graph.
- Candidate 2: tiny Gemma 4 E2B block from the static executor after the integration namespace is imported.
- Candidate 3: Gemma 4 E2B frozen-forward subgraph only after model license, storage, and cache gates pass.

## Inputs And Outputs

Inputs, outputs, tensor dtypes, and tolerances must be copied from the imported `executor_ir` examples before any compile command runs.

## Target SoC

RedMagic 10 Pro / Snapdragon SM8750. RunPod is a compile and manifest lane only; the phone is the authority device.

## Expected Output Artifact Path

Remote compile outputs, if later run, must stay outside git by default and be summarized under:

`runtime/reports/gemma4_megakernel/runpod/<run_id>/`

Large binary artifacts require an explicit artifact policy before transfer.

## Correctness Comparator

Mac or RunPod CPU/PyTorch golden vectors first, then RedMagic backend output comparison. Performance results are ignored until parity passes.

## Phone Deployment Plan

No deployment in this setup gate. Any future deployment must preserve existing phone binaries by checksum and write a rollback path before replacement.

## Rollback Plan

No files were deployed to the phone. Future phone runs must keep previous binaries under timestamped names and record checksums before overwrite.
