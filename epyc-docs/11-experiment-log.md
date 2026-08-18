# 11 — Experiment Log

This is a reconstructed chronological ledger. Exact dates are omitted where the original timestamp was not retained.

## EXP-001 — Baseline MimicOS/MMU sanity

Purpose: verify baseline translation stack.

Result: representative run reported 73 VA→PA and 73 PA→VA mappings with zero violations.

Verdict: PASS.

## EXP-002 — Reduced EPYC cache configs

Artifacts: 4core-2way, 4core-4way, 8core-ccd, 16core-2ccd.

Purpose: isolate cache sharing/topology before full 128-core simulation.

## EXP-003 — Shared L3 tests

Benchmarks: `shared_l3_test.cpp`, `shared_l3_8core_test.cpp`.

Verdict: sufficiently stable to proceed; hardware calibration remains pending.

## EXP-004 — DRAM distribution/stream tests

Benchmarks: `dram_distribution_test.cpp`, `dram_stream_test.c`.

A recorded 16-thread run completed with checksum, ~23.3M instructions and ~8.7M cycles while exercising millions of cache lines.

Verdict: PASS for functional multi-controller traffic.

## EXP-005 — Affinity validation

Benchmark: `sniper_affinity_test.c`.

Requested socket-separated core groups including 0–7 and 64–71. Per-core instructions confirmed targeted execution.

Verdict: PASS.

## EXP-006 — NUMA allocator activation

Representative allocator stats:

```text
four_kb_allocated = 32852
local_allocs      = 32852
node0_allocs      = 16468
node1_allocs      = 16384
```

Verdict: NUMA allocator active.

## EXP-007 — Initial NUMA DRAM accounting

Both node0 and node1 counters appeared, but whole-run traffic mixed placement, metadata and measurement.

Verdict: dedicated latency benchmark required.

## EXP-008 — Early REMOTE0 long pointer chase

Working set: 64 MiB. Early traversal count: 8.

Successful run required ~1760 s ROI and ~1798 s wall time.

Lesson: reduce traversals while debugging.

## EXP-009 — ROI-stat delta attempt

Some DRAM metrics lacked `roi-begin` rows, causing null/zero deltas.

Verdict: method rejected for those metrics.

## EXP-010 — App/page-table identity

Core 0 and 64 both reported app 0 and the same page-table pointer.

Verdict: separate-page-table hypothesis rejected.

## EXP-011 — Explicit benchmark phase markers

Observed correct FIRST_TOUCH_BEGIN/END and CHASE_BEGIN/END ordering.

Verdict: PASS.

## EXP-012 — Array-specific VA→PA filtering

REMOTE0:

```text
FIRST_TOUCH core64 node1 = 67/67
CHASE       core0  node1 = 22/22
```

Representative same mapping: PPN 134119423, PA 0x7fe7fff000.

Verdict: PASS.

## EXP-013 — Chase DRAM instrumentation with inherited NUCA

DRAM chase count zero while phase marker fired. Core 0 showed ~525k NUCA hits.

Verdict: traffic intercepted before DRAM.

## EXP-014 — NUCA explicitly disabled

DRAM trace showed requester=0, requester_node=0, selected_node=1, local=0. ~525k loads moved to DRAM_REMOTE.

Verdict: PASS.

## EXP-015 — Four-way NUMA suite

LOCAL0 44.50 ns; REMOTE0 51.58 ns mixed average; LOCAL1 44.54 ns; REMOTE1 51.52 ns mixed average.

Verdict: PASS.

## EXP-016 — Effective latency telemetry

Registered `numa_node0_total_latency` and `numa_node1_total_latency`. Weighted averages matched the expected effect of +40 ns on only the remote subset.

Verdict: PASS.

## Milestone

Functional dual-socket NUMA model frozen and saved in Git at the validated checkpoint.
