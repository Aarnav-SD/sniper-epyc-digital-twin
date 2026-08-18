# 16 — Evidence Index

This record was reconstructed from terminal outputs, saved logs, working-session history and the validated simulator state.

High-value evidence includes:

- MMU sanity: representative 73 VA→PA and 73 PA→VA mappings with zero violations.
- Larger multi-thread runs with thousands/tens of thousands of clean mappings.
- Affinity syscall/scheduler inspection and target-core instruction counts.
- resolved NUMA allocator: 2 nodes, 256 GiB each, LOCAL policy.
- explicit benchmark marker sequence.
- REMOTE0 array-specific translation proof: first-touch and chase use node1 physical pages.
- live DRAM trace: `requester=0 requester_node=0 selected_node=1 local=0`.
- `HitWhere` shift after disabling generic NUCA: ~525k accesses move from NUCA to DRAM_REMOTE.
- final four-way effective latency results: 44.50 / 51.58 / 44.54 / 51.52 ns.
- per-node effective latency statistic exposed after the penalty.
- Git checkpoint saved and tagged `numa-validation-v1`.

## Reconstruction caution

Some early chronology was reconstructed from saved output rather than a contemporaneous lab notebook. Where an exact date was not guaranteed, this documentation records functional ordering rather than inventing timestamps.
