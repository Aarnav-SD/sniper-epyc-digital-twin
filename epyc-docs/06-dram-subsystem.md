# 06 — DRAM Subsystem

## Objective

Model the dual-socket DDR4 subsystem with enough visibility for bandwidth, controller-distribution, NUMA and later DRAM-power studies.

Important configs:

- `ddr4_3200_8controllers.cfg`
- `ddr4_3200_16controllers.cfg`

The validated full-node stack uses the 16-controller setup.

## Benchmarks

- `dram_distribution_test.cpp`
- `dram_stream_test.c`

A recorded 16-thread run completed with a checksum, ~23.3M simulated instructions and ~8.7M cycles while exercising millions of unique cache lines and preserving MMU consistency.

## Controller construction

`MemoryManager` was inspected to verify that when NUMA or CXL is enabled it constructs `TieredDramCntlr`, not ordinary `DramCntlr`. This invalidated the hypothesis that NUMA traffic was silently going through the wrong controller class.

## DRAM read path

The directory sends `DRAM_READ_REQ` with the original CPU requester preserved. Runtime validation later showed a core-0 access arrive as:

```text
requester=0
requester_node=0
selected_node=1
local=0
```

## Underlying vs effective latency

The underlying `DramPerfModel` measures base latency before the NUMA penalty. Therefore its `total-access-latency-data` metric is not the final latency returned by the tiered NUMA controller.

The NUMA node's post-penalty accumulator is now exposed as:

```text
numa_node0_total_latency
numa_node1_total_latency
```
