# 04 — EPYC Core Model

## Target

AMD EPYC 7763, Milan/Zen 3 generation, two 64-core sockets.

The model does not claim cycle-identical pipeline fidelity. It is intended to reproduce important organization and generate calibratable timing/activity signatures.

## Progressive scaling

Development deliberately used reduced configs before 128 cores:

- 4-core tests;
- 8-core CCD-oriented tests;
- 16-core multi-CCD tests;
- full 128-core dual-socket runs.

This reduced debugging cost and isolated topology problems before full-node experiments.

## Affinity

NUMA validation required controlled placement. Sniper's `sched_setaffinity` syscall path and pinned scheduler were inspected. A custom benchmark requested cores in two separated groups, including 0–7 and 64–71. Per-core instruction statistics then confirmed work on the intended simulated cores.

Status:

- core count/socket partition: **VALIDATED for NUMA experiments**
- detailed core timing fidelity vs hardware: **NOT YET CALIBRATED**
- per-core power: **NOT YET CALIBRATED**
