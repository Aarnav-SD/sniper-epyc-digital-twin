# 13 — Source-Code Modifications

Modified files visible at the validated checkpoint included:

## `common/core/memory_subsystem/cache/cache.cc`

Cache-hierarchy / diagnostic work. Review remaining debug-only modifications during cleanup.

## `common/core/memory_subsystem/dram/dram_cntlr_interface.cc`

DRAM request-handling observability and routing investigation.

## `common/core/memory_subsystem/parametric_dram_directory_msi/cache_cntlr.cc`

Cache/DRAM path investigation and diagnostics.

## `common/core/memory_subsystem/parametric_dram_directory_msi/mmu_designs/mmu.cc`

Major validation instrumentation:

- mapping sanity;
- app/page-table diagnostics;
- benchmark marker hook;
- phase-aware VA→PA logging.

## `common/core/memory_subsystem/parametric_dram_directory_msi/nuca_cache.cc`

NUCA behavior/stat investigation.

## `common/core/memory_subsystem/pr_l1_pr_l2_dram_directory_msi/dram_cntlr.cc`

DRAM timing/path diagnostics.

## `common/core/memory_subsystem/pr_l1_pr_l2_dram_directory_msi/dram_directory_cntlr.cc`

Used to trace:

- NUCA-before-DRAM behavior;
- DRAM_READ_REQ;
- requester propagation;
- DRAM write paths.

## `common/core/memory_subsystem/pr_l1_pr_l2_dram_directory_msi/tiered_dram_cntlr.cc`

Core NUMA implementation:

- node initialization;
- per-node DRAM models;
- core→node mapping;
- PFN→node mapping;
- local/remote classification;
- additive remote latency;
- per-node counters;
- effective `total_latency` telemetry;
- temporary phase-aware diagnostics.

Keep reusable stats; remove or gate benchmark-specific logging.

## `include/memory_management/physical_memory_allocators/numa_reserve_thp.h`

NUMA-aware reservation/THP allocator with per-node capacities, kernel reservations, policies and accounting.

## Supporting allocator/policy work

The branch also depends on allocator-factory support, NUMA policy parsing, `NumaReserveTHPSniperPolicy`, buddy-policy specialization and per-node allocator stats.

## Benchmark sources

- `dram_distribution_test.cpp`
- `dram_stream_test.c`
- `numa_latency_test.cpp`
- `numa_local_remote_test.c`
- `shared_l3_8core_test.cpp`
- `shared_l3_test.cpp`
- `sniper_affinity_test.c`

Compiled binaries should remain ignored.

## Cleanup procedure

1. remove/gate temporary logging;
2. keep reusable telemetry/invariants;
3. rebuild;
4. rerun LOCAL0/REMOTE0/LOCAL1/REMOTE1;
5. compare against checkpoint;
6. create a clean post-debug tag.
