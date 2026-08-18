# 05 — Cache Hierarchy and CCD Modeling

## Goal

Represent Milan's grouped shared-L3 organization rather than one monolithic LLC across all 128 cores. The working abstraction uses 8-core shared-L3/CCD-oriented groups.

## Development artifacts

Benchmarks:

- `shared_l3_test.cpp`
- `shared_l3_8core_test.cpp`

Reduced configs:

- `epyc7763-4core-2way.cfg`
- `epyc7763-4core-4way.cfg`
- `epyc7763-8core-ccd.cfg`
- `epyc7763-16core-2ccd.cfg`
- `epyc7763-dualsocket.cfg`

## Important NUCA discovery

The resolved Sniper configuration inherited:

```ini
[perf_model/nuca]
enabled = true
cache_size = 8192
associativity = 16
```

This was not an intentional Milan modeling choice.

During REMOTE0, core 0 initially showed roughly:

```text
~525k NUCA hits
~523k CACHE_REMOTE hits
almost no remote DRAM
```

The directory checks NUCA before issuing DRAM requests, so the inherited NUCA was masking the remote-DRAM path.

## Resolution

The EPYC config now explicitly sets:

```ini
[perf_model/nuca]
enabled = false
```

Afterward, approximately the same ~525k accesses moved from NUCA to `loads-where-data-dram-remote`.

## Status

- reduced cache topology testing: **SUPPORTED / partially validated**
- 8-core shared-L3 abstraction: **IMPLEMENTED**
- generic Sniper NUCA as Milan structure: **INVALIDATED**
- explicit NUCA disable for EPYC: **VALIDATED as necessary for clean NUMA DRAM behavior**
