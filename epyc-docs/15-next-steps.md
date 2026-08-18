# 15 — Next Steps

## Immediate cleanup

Remove or compile-time gate temporary diagnostics such as:

- DEBUG NUMA MAP
- DEBUG REMOTE0
- DEBUG CHASE DRAM
- benchmark VA→PA dumps
- phase prints

Retain reusable NUMA counters, effective total latency and useful MMU invariants.

## Hardware calibration

On the real EPYC 7763 node, measure:

- socket0 local pointer-chase latency;
- socket1 local pointer-chase latency;
- socket0→socket1 remote latency;
- socket1→socket0 remote latency;
- bandwidth scaling with thread count;
- controller/channel saturation.

Use explicit affinity and first-touch placement where permitted.

## DDR4 calibration

Calibrate base latency, queueing, row behavior if observable, bandwidth and controller scaling.

## Cache calibration

Validate private L1/L2, 8-core L3 sharing domain, same-CCD vs cross-CCD behavior and cache-to-cache transfers.

## CPU activity and power

Extract IPC, cache misses, branches, stalls, memory activity and active-time/frequency statistics from representative workloads.

Map these to McPAT, then calibrate raw McPAT output against real telemetry.

## SST integration

Once calibrated, derive reduced node models suitable for hundreds of nodes. Sniper becomes the detailed oracle/profile generator rather than the simulator executed for all 420 CPU nodes continuously.

## Validation discipline

```text
assumption
→ implementation
→ minimal microbenchmark
→ internal telemetry
→ real-hardware comparison
→ calibrated parameter
→ regression test
```
