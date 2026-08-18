# 00 — Project Overview

## Research objective

Build a research-grade digital twin of the internship HPC, beginning with an accurate model of the real CPU compute node. The current philosophy is to model the reference cluster faithfully first and generalize through configuration later.

The node model is expected to expose per-core timing, cache activity, address translation, page-table behavior, memory-controller activity, NUMA locality, memory latency/bandwidth, and later per-core/per-socket power.

## Why Sniper was modified

Stock Sniper provides a strong multicore timing framework, but the target EPYC 7763 node required more than scalar config changes. The work therefore combines:

1. configuration-level modeling;
2. source instrumentation;
3. source extensions for NUMA-aware allocation and DRAM locality;
4. custom microbenchmarks;
5. SQLite-based statistics analysis.

The target is not a generic “EPYC-like” model; it is a defensible model whose assumptions and validation evidence are explicit.

## Current scope

Implemented focus:

- 128 cores;
- two sockets / NUMA nodes;
- private/shared cache hierarchy;
- physical memory allocation;
- virtual-to-physical translation;
- DDR4 timing;
- multiple DRAM controller locations;
- NUMA local/remote behavior.

Not yet completed:

- McPAT calibration;
- per-core power fitting;
- GPU-node modeling;
- InfiniBand;
- Lustre;
- PBS scheduling at cluster scale;
- SST cluster integration;
- rack/facility power/cooling.

## Development method

The project evolved into:

> architecture assumption → implementation → microbenchmark → internal instrumentation → statistics → hypothesis update

Several early interpretations were wrong even when the implementation was correct. Those failed hypotheses are retained because they reveal important simulator-observability pitfalls.
