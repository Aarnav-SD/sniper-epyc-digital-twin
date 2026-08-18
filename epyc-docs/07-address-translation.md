# 07 — Address Translation, MMU, and Physical Memory

## Baseline

The active translation stack includes MimicOS, a four-level radix page table, 4 KiB/2 MiB page support, TLBs, page-walk caches, and a physical allocator.

## MMU sanity instrumentation

The MMU was instrumented to track VA→PA and PA→VA consistency. Representative early result:

```text
Core 0 checked 73 unique VA->PA mappings,
73 unique PA->VA mappings,
0 violations detected
```

Larger workloads later exercised many more mappings with zero reported violations.

## Why translation became a NUMA suspect

Early NUMA counters did not match expectations, so hypotheses included:

- wrong-node allocation;
- different page tables per worker;
- cross-core VA→PA inconsistency;
- PA corruption before DRAM.

## Application/page-table identity

Diagnostics showed core 0 and core 64 using the same application ID and same page-table object during the benchmark. Separate-address-space behavior was therefore invalidated.

## Explicit phase markers

`MagicServer::inROI()` was too broad for the desired microbenchmark phase. The benchmark was changed to emit:

```text
FIRST_TOUCH_BEGIN
FIRST_TOUCH_END
CHASE_BEGIN
CHASE_END
```

using `SimMarker()`, with `HOOK_MAGIC_MARKER` callbacks in Sniper.

## Array-only filtering

Phase filtering still included stack/runtime/page-table traffic. The benchmark therefore printed its array range and MMU logs were filtered to VAs inside that exact 64 MiB region.

REMOTE0 then showed:

```text
FIRST_TOUCH core64 → node1: 67/67 sampled array translations
CHASE       core0  → node1: 22/22 sampled array translations
```

A representative page matched exactly in both phases:

```text
PPN 134119423
PA  0x7fe7fff000
```

## Conclusion

Cross-core translation inconsistency was **INVALIDATED** as the cause of the NUMA anomaly.
