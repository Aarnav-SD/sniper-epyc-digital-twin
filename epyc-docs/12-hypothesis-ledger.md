# 12 — Hypothesis Ledger

| ID | Hypothesis | Status | Resolution |
|---|---|---|---|
| H-001 | baseline MMU may generate inconsistent mappings | INVALIDATED | repeated zero-violation sanity checks |
| H-002 | simulated affinity may ignore requested CPUs | INVALIDATED | scheduler path + per-core instructions confirmed affinity |
| H-003 | old reserve_thp allocator may still be active | INVALIDATED | resolved config/stats confirmed `numa_reserve_thp` |
| H-004 | core0/core64 may use different page tables | INVALIDATED | same app and PT pointer |
| H-005 | core0 may remap chase array to node0 | INVALIDATED | array-only VA→PA logs preserve node1 placement |
| H-006 | requester may become directory/controller core | INVALIDATED for validated read path | DRAM trace preserved requester=0 |
| H-007 | TieredDramCntlr may not be instantiated | INVALIDATED | MemoryManager construction verified |
| H-008 | base DramCntlr may be called due to bad virtual dispatch | INVALIDATED | virtual interface/override + construction verified |
| H-009 | zero chase DRAM means MMU is broken | INVALIDATED | generic NUCA intercepted traffic |
| H-010 | generic Sniper NUCA is suitable for Milan model | INVALIDATED for current model | inherited unintentionally; masked DRAM |
| H-011 | all phase-filtered translations belong to benchmark array | INVALIDATED | runtime/stack accesses also present |
| H-012 | underlying DRAM average should show +40 ns directly | INVALIDATED interpretation | metric recorded before NUMA penalty |
| H-013 | REMOTE0 should create node1 remote traffic | VALIDATED | ~526k node1 remote accesses |
| H-014 | REMOTE1 should create node0 remote traffic | VALIDATED | ~526k node0 remote accesses |
| H-015 | LOCAL0 and LOCAL1 should be symmetric | VALIDATED | 44.50 vs 44.54 ns |
| H-016 | REMOTE0 and REMOTE1 should be symmetric | VALIDATED | 51.58 vs 51.52 ns mixed averages |
| H-017 | +40 ns is functionally applied to remote accesses | VALIDATED | code path + effective weighted totals |
| H-018 | 40 ns matches real EPYC 7763 remote penalty | NOT YET VALIDATED | requires hardware calibration |
| H-DRAM-001 | NUMA page placement and local/remote latency classification are correct, but DRAM-controller selection remains globally interleaved across all 16 controllers. Consequently, a workload whose pages reside entirely on one NUMA node can consume bandwidth from controllers belonging to both sockets. | VALIDATED | to be seen |
