# 14 — Current Validation Status

| Property | Status |
|---|---|
| 128-core execution | VALIDATED |
| 2-socket / 2-NUMA partition | VALIDATED |
| cores 0–63 → node0 | VALIDATED |
| cores 64–127 → node1 | VALIDATED |
| 4-level radix page table | IMPLEMENTED / exercised |
| 4 KiB / 2 MiB support | IMPLEMENTED |
| VA→PA consistency | VALIDATED |
| shared app page table across workers | VALIDATED |
| NUMA-aware allocator | VALIDATED functionally |
| node0/node1 physical ranges | VALIDATED |
| requester preservation | VALIDATED |
| local/remote DRAM classification | VALIDATED |
| remote penalty application | VALIDATED functionally |
| 40 ns hardware fidelity | NOT YET CALIBRATED |
| generic NUCA as EPYC structure | INVALIDATED |
| 16-controller DDR4 topology | IMPLEMENTED / functionally exercised |
| DDR4 timing accuracy | NOT YET CALIBRATED |
| L1/L2/L3 topology | IMPLEMENTED / partially validated |
| L3/CCD timing fidelity | NOT YET CALIBRATED |
| cache-to-cache remote behavior | SUPPORTED |
| per-core power | NOT YET CALIBRATED |
| McPAT integration | PLANNED |
| SST cluster integration | PLANNED |
| GPU node | PLANNED |
| network/Lustre/PBS | PLANNED |

## Freeze decision

Basic NUMA plumbing should remain frozen except for debug cleanup, evidence-driven calibration and telemetry improvements that do not alter routing semantics.
