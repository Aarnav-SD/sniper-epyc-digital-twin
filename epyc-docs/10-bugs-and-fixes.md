# 10 — Bugs, Failure Modes, and Fixes

## BUG-001 — Unintended generic NUCA inherited from base config

**Observation:** REMOTE0 barely reached remote DRAM.

**Competing hypotheses:** requester corruption, MMU inconsistency, wrong controller class, dispatch bug.

**Root cause:** `config/base.cfg` enabled generic NUCA. The directory checked it before DRAM, causing ~525k pointer-chase loads to terminate there.

**Fix:** explicitly set `[perf_model/nuca] enabled=false` for the EPYC config.

**Regression:** roughly the same ~525k accesses became `DRAM_REMOTE`.

**Status:** FIXED / VALIDATED.

---

## BUG-002 — Phase logs polluted by runtime traffic

**Observation:** raw phase logs mixed node0/node1 translations.

**Incorrect interpretation:** array might be split across nodes.

**Root cause:** phase filtering selected time, not address range.

**Fix:** print array `[base,end)` and filter MMU records to that range.

**Result:** all sampled benchmark-array translations in REMOTE0 were node1.

---

## BUG-003 — `inROI()` unsuitable as benchmark-phase selector

**Observation:** debug quotas were consumed before the pointer chase.

**Fix:** `SimMarker()` + `HOOK_MAGIC_MARKER` explicit phases.

---

## BUG-004 — Source/binary diagnostic mismatch

**Observation:** source contained `[DEBUG DRAM PHASE]` but `strings lib/sniper` did not.

**Fix:** force rebuild and verify diagnostic strings before rerunning.

---

## BUG-005 — Suspected separate page tables

**Hypothesis:** core 0 and core 64 used different address spaces.

**Evidence:** same app ID and page-table pointer.

**Status:** INVALIDATED; no fix needed.

---

## BUG-006 — Base DRAM latency misread as NUMA-effective latency

**Observation:** remote underlying DRAM average remained ~41–45 ns.

**Root cause:** `DramPerfModel` records before the NUMA penalty.

**Fix:** expose `NumaNodeInfo::total_latency` as per-node stats.

**Status:** FIXED / VALIDATED.

---

## BUG-007 — C benchmark compiled against C++ API with `gcc`

**Error:** `unordered_map: No such file or directory`.

**Fix:** rename benchmark to `.cpp` and compile with `g++`.

---

## BUG-008 — Early pointer chase exceeded timeout

An 8-traversal REMOTE0 run required about 1760 s ROI / ~1798 s wall time. Debug traversal count was reduced and timeouts increased.

---

## BUG-009 — Temporary diagnostic used nonexistent `m_cores_per_numa_node`

**Symptom:** build failure in `tiered_dram_cntlr.cc`.

**Fix:** use real core-to-node helper/config mapping.

---

## BUG-010 — ROI subtraction yielded null/zero DRAM deltas

Some metrics existed only at `roi-end`/`stop`, not `roi-begin`.

**Fix:** use stop snapshots for whole-run metrics and marker-aware diagnostics for phase-specific evidence.
