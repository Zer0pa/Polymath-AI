# P14-5 Blockers

P14-5 passes only for the repaired full-teacher subset objective path.

The full 1024-train-shard plus 128-heldout-shard teacher campaign is not
complete and is not promoted. The clean RunPod environment has no GPU available,
and the observed CPU time for one complete 8-sequence shard was 471 seconds,
which projects to roughly 150.72 serial hours for all 1152 shards.

P14-6 is therefore constrained to a predeclared short proof over generated
full-teacher subset shards. P14-7 remains blocked until P14-6 passes and the
larger shard generation/deployment plan is explicit.

No fridge, freezer, ice, or other non-OEM cooling path was used or promoted in
this gate.
