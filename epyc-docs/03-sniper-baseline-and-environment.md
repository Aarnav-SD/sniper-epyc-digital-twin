# 03 — Sniper Baseline and Environment

## Git baseline

The working tree originates from official SniperSim.

Recommended remote layout:

```text
origin   → private modified EPYC repo
upstream → official snipersim/snipersim
```

Known-good milestone tag:

```text
numa-validation-v1
```

## Main config stack

```bash
./run-sniper \
  -n 128 \
  -caddress_translation_schemes/baseline \
  -c~/hpc-configs/config/epyc7763-dualsocket.cfg \
  -c~/hpc-configs/config/ddr4_3200_16controllers.cfg \
  -c~/hpc-configs/config/epyc7763-numa.cfg \
  -- <benchmark>
```

The baseline translation stack indirectly inherits `config/base.cfg`. This mattered because base.cfg enabled generic NUCA even though the EPYC-specific configs had not intentionally selected it.

## Translation baseline

Early runs instantiated:

- MimicOS;
- reserve-THP allocator;
- 4-level radix page table;
- 4 KiB / 2 MiB page support;
- TLB/page-walk infrastructure;
- SIFT trace-driven execution.

Representative early MMU sanity result:

```text
73 unique VA→PA mappings
73 unique PA→VA mappings
0 violations
```

Larger workloads later exercised thousands/tens of thousands of mappings without reported consistency violations.

## Run-output policy

Simulation results belong under `~/sniper-runs/` and should not be committed. Commit source, configs, benchmark source, compact result summaries, and docs.
