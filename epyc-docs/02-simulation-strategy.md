# 02 — Simulation Strategy

## Finalized stack

- **SST** — eventual cluster-scale framework.
- **Sniper** — detailed CPU-node timing/activity model.
- **McPAT** — planned CPU power derivation.
- **gem5** — selective higher-fidelity validation.
- **Real telemetry** — calibration target.

## Intended workflow

```text
Sniper detailed runs
      ↓
activity/timing signatures
      ↓
McPAT raw power estimates
      ↓
calibration to real telemetry
      ↓
reduced parameterized node model
      ↓
SST full-cluster digital twin
```

Running detailed simulation for all 420 CPU nodes continuously is not the intended final architecture.

## Fidelity levels

### Level 1 — aggregate node

Useful for cluster sweeps: utilization, bandwidth, network/storage traffic, node power, temperature proxies.

### Level 2 — socket/NUMA

Now substantially implemented and validated: local/remote memory, socket placement, cross-socket traffic, per-node memory telemetry.

### Level 3 — microarchitecture

Sniper exposes IPC, cache behavior, translation, memory-controller activity, timing and stalls. This is the high-fidelity oracle/profile source.

## Calibration principle

Functional correctness and hardware calibration are separate. `remote_latency_ns = 40` is now proven to be added correctly, but the value 40 ns itself is still a calibration parameter until compared against the real EPYC system.
