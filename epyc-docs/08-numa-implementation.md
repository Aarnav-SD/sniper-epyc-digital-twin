# 08 — NUMA Implementation

## Goal

Implement two-node NUMA behavior with:

- per-node capacity;
- first-touch placement;
- core→node mapping;
- PA→node mapping;
- local/remote classification;
- additive remote latency;
- per-node telemetry.

## Current configuration

```ini
[perf_model/dram/numa]
enabled = true
num_nodes = 2
cores_per_node = 64
remote_latency_ns = 40

[perf_model/dram/numa/node0]
capacity_gb = 256
kernel_reserved_gb = 16
tier_id = 0
type = "ddr"

[perf_model/dram/numa/node1]
capacity_gb = 256
kernel_reserved_gb = 16
tier_id = 0
type = "ddr"
```

Allocator settings include:

```text
num_numa_nodes = 2
numa_policy = local
per_node_capacity_mb = 262144,262144
per_node_kernel_mb = 16384,16384
```

## NUMA-aware allocator

`numa_reserve_thp` supports policy parsing for LOCAL, BIND, INTERLEAVE and PREFERRED. The validated experiments use LOCAL first-touch behavior.

## Core mapping

With `cores_per_node=64`:

```text
cores 0–63   → node 0
cores 64–127 → node 1
```

## PFN mapping

At 256 GiB/node and 4 KiB granularity:

```text
node0 PFN [0, 67108864)
node1 PFN [67108864, 134217728)
```

## Remote latency path

Conceptually:

```cpp
access_latency = node.perf_model->getAccessLatency(...);
if (!isLocalAccess(requester, address)) {
    access_latency += m_numa_remote_latency;
    node.remote_accesses++;
} else {
    node.local_accesses++;
}
node.total_latency += access_latency;
```

## Telemetry

Per-node statistics include:

- reads
- writes
- local accesses
- remote accesses
- effective total latency

All core plumbing above is functionally **VALIDATED**. The numerical 40 ns value still requires real-hardware calibration.
