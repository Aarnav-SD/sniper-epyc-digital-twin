# 01 — Reference Hardware

## CPU node

Reference CPU server:

- Dell PowerEdge R6525
- 2 × AMD EPYC 7763 (Milan)
- 64 cores/socket
- 128 cores/node
- ~2.45 GHz nominal frequency
- 512 GiB DDR4
- 600 GB SAS local disk
- RHEL 8.7 on the internship system

Current simulator abstraction:

```text
NUMA node 0 / socket 0: cores 0–63, 256 GiB modeled memory
NUMA node 1 / socket 1: cores 64–127, 256 GiB modeled memory
```

16 GiB of kernel memory is reserved per node in the current NUMA configuration.

## Cluster context

Known cluster scale:

- 420 CPU nodes
- 12 GPU nodes
- GPU node: Dell EMC PowerEdge XE8545
- 4 × NVIDIA A100 80 GB per GPU node
- InfiniBand fat-tree
- separate OS/hardware management network
- Lustre parallel storage
- PBS Pro

The detailed CPU-node model is intended to become a calibrated reference component inside the larger digital twin.

## Modeling warning

A configured simulator component must not be described as a faithful physical EPYC component merely because its size is similar. This became critical when Sniper's generic NUCA cache was inherited from the base config: it changed memory behavior substantially but did not correspond cleanly to the intended Milan hierarchy.
