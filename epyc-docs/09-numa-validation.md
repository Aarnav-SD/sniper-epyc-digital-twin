# 09 — NUMA Validation

## Objective

Prove end-to-end that first-touch placement, cross-core translation, requester propagation, locality classification and latency addition all work in both socket directions.

## Benchmark

`numa_latency_test.cpp` uses a 64 MiB working set, explicit initializer and reader cores, a pointer chase, and explicit phase markers.

Four cases:

```text
LOCAL0:  first-touch 0,  reader 0
REMOTE0: first-touch 64, reader 0
LOCAL1:  first-touch 64, reader 64
REMOTE1: first-touch 0,  reader 64
```

## Translation proof

REMOTE0 array-only logs showed the same node-1 PA used by core 64 during first touch and core 0 during the chase. This directly proved that physical placement survives the cross-core transition.

## NUCA interference

With generic NUCA enabled, core 0 showed roughly 525k NUCA hits and almost no remote DRAM. The pointer chase was therefore not cleanly exercising remote DRAM.

After explicit NUCA disable, runtime DRAM traces showed:

```text
requester=0 requester_node=0 selected_node=1 local=0
```

and core 0 reported ~525k `loads-where-data-dram-remote`.

## Final results

| Experiment | Dominant node | Local accesses | Remote accesses | Effective avg latency |
|---|---:|---:|---:|---:|
| LOCAL0 | 0 | 2,891,570 | 28 | 44.50 ns |
| REMOTE0 | 1 | 1,575,918 | 526,381 | 51.58 ns |
| LOCAL1 | 1 | 2,888,598 | 0 | 44.54 ns |
| REMOTE1 | 0 | 1,578,818 | 526,500 | 51.52 ns |

Local symmetry:

```text
44.50 ns vs 44.54 ns
```

Remote mixed-average symmetry:

```text
51.58 ns vs 51.52 ns
```

## Why remote mixed averages are not ~84 ns

The per-node average contains both local and remote accesses. In REMOTE0 only about 25% of node-1 accesses were remote. Only that fraction receives +40 ns, so the node-wide average rises by roughly 10 ns relative to the base latency for that workload.

## Verdict

- first-touch placement: PASS
- cross-core VA→PA consistency: PASS
- requester propagation: PASS
- core→node mapping: PASS
- PA→node mapping: PASS
- local/remote classification: PASS
- both remote directions: PASS
- remote penalty path: PASS
- effective latency accounting: PASS
- bidirectional symmetry: PASS
