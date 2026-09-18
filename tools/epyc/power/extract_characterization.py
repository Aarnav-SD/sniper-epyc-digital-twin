#!/usr/bin/env python3

import argparse
import configparser
import json
import re
import sys
from pathlib import Path

SNIPER_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SNIPER_ROOT / "tools"))

import sniper_lib


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def numeric_sum(value):
    total = 0.0
    for x in as_list(value):
        try:
            total += float(x)
        except (TypeError, ValueError):
            pass
    return total


def get_stat(results, *names):
    for name in names:
        if name in results:
            return results[name]
    return None


def per_kinst(value, instructions):
    if instructions <= 0:
        return None
    return value / (instructions / 1000.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("resultsdir", type=Path)
    parser.add_argument("--workload", default=None)

    # Experimental metadata. Prefer this over inferring intended
    # parallelism from simulator housekeeping activity.
    parser.add_argument("--active-cores", type=int, default=None)

    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    resultsdir = args.resultsdir.resolve()

    if not (resultsdir / "sim.cfg").exists():
        raise SystemExit(f"Missing {resultsdir / 'sim.cfg'}")

    if not (resultsdir / "sim.stats.sqlite3").exists():
        raise SystemExit(f"Missing {resultsdir / 'sim.stats.sqlite3'}")

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(resultsdir / "sim.cfg")

    total_cores = cfg.getint("general", "total_cores")
    frequency_ghz = cfg.getfloat("perf_model/core", "frequency")

    results = sniper_lib.get_results(
        resultsdir=str(resultsdir)
    )["results"]

    # --------------------------------------------------------------
    # Execution
    # --------------------------------------------------------------

    instruction_vector = as_list(
        get_stat(
            results,
            "performance_model.instruction_count",
            "core.instructions",
        )
    )

    elapsed_vector = as_list(
        get_stat(
            results,
            "performance_model.elapsed_time",
        )
    )

    nonidle_elapsed_vector = as_list(
        get_stat(
            results,
            "performance_model.nonidle_elapsed_time",
        )
    )

    global_time_vector = as_list(
        get_stat(
            results,
            "global.time",
        )
    )

    total_instructions = numeric_sum(instruction_vector)

    # Architectural instruction-active cores are used only to interpret
    # Sniper execution statistics. This is intentionally distinct from
    # args.active_cores, which records experimental workload parallelism.
    instruction_active_indices = [
        i for i, x in enumerate(instruction_vector)
        if float(x or 0) > 0
    ]

    instruction_active_cores = len(
        instruction_active_indices
    )

    active_cores = args.active_cores

    # Sniper time statistics are in femtoseconds.
    duration_fs = max(
        float(x or 0)
        for x in global_time_vector
    )

    duration_s = (
        duration_fs * 1e-15
        if duration_fs > 0
        else None
    )

    # McPAT derives per-core cycles from elapsed_time and the configured
    # core frequency. Use the same timing semantics here.
    frequency_hz = frequency_ghz * 1e9

    active_core_cycles = 0.0
    active_core_nonidle_cycles = 0.0

    for i in instruction_active_indices:
        if i < len(elapsed_vector):
            active_core_cycles += (
                float(elapsed_vector[i] or 0)
                * 1e-15
                * frequency_hz
            )

        if i < len(nonidle_elapsed_vector):
            active_core_nonidle_cycles += (
                float(nonidle_elapsed_vector[i] or 0)
                * 1e-15
                * frequency_hz
            )

    aggregate_active_ipc = (
        total_instructions
        / active_core_nonidle_cycles
        if active_core_nonidle_cycles > 0
        else None
    )

    active_core_utilization = (
        active_core_nonidle_cycles
        / active_core_cycles
        if active_core_cycles > 0
        else None
    )

    instruction_rate_gips = (
        total_instructions
        / duration_s
        / 1e9
        if duration_s and duration_s > 0
        else None
    )

    # --------------------------------------------------------------
    # Cache
    # --------------------------------------------------------------

    l3_loads = numeric_sum(
        get_stat(results, "L3.loads-data", "L3.loads")
    )
    l3_stores = numeric_sum(
        get_stat(results, "L3.stores-data", "L3.stores")
    )
    l3_load_misses = numeric_sum(
        get_stat(results, "L3.load-misses-data")
    )
    l3_store_misses = numeric_sum(
        get_stat(results, "L3.store-misses-data")
    )

    l3_accesses = l3_loads + l3_stores
    l3_misses = l3_load_misses + l3_store_misses

    # --------------------------------------------------------------
    # DRAM
    #
    # Final EPYC NPS4 model exposes:
    #
    #   dram.total-accesses-data
    #   dram-numaN.total-accesses-data
    #
    # The latter represent the additional NPS-local controller models.
    # Sum each controller-level data-access counter exactly once.
    # Do NOT sum ranks/banks because those are lower-level views of
    # the same requests.
    # --------------------------------------------------------------

    dram_controller_pattern = re.compile(
        r"^dram(?:-numa\d+)?\.total-accesses-data$"
    )

    dram_controller_accesses = {}

    for name, value in results.items():
        if dram_controller_pattern.match(name):
            dram_controller_accesses[name] = numeric_sum(value)

    dram_accesses = sum(dram_controller_accesses.values())

    # NUMA classifier counters provide read/write information.
    numa_reads = {}
    numa_writes = {}

    read_pattern = re.compile(r"^dram\.numa_node(\d+)_reads$")
    write_pattern = re.compile(r"^dram\.numa_node(\d+)_writes$")

    for name, value in results.items():
        m = read_pattern.match(name)
        if m:
            numa_reads[m.group(1)] = numeric_sum(value)

        m = write_pattern.match(name)
        if m:
            numa_writes[m.group(1)] = numeric_sum(value)

    dram_reads = sum(numa_reads.values())
    dram_writes = sum(numa_writes.values())

    # --------------------------------------------------------------
    # Record
    # --------------------------------------------------------------

    record = {
        "schema_version": 1,

        "source": {
            "type": "sniper",
            "results_dir": str(resultsdir),
            "workload": args.workload or resultsdir.parent.name,
        },

        "hardware": {
            "total_cores": total_cores,
            "frequency_ghz": frequency_ghz,
        },

        "execution": {
            "active_cores": active_cores,
            "instruction_active_cores": instruction_active_cores,
            "total_instructions": total_instructions,
            "duration_s": duration_s,
            "instruction_rate_gips": instruction_rate_gips,
            "active_core_cycles": active_core_cycles,
            "active_core_nonidle_cycles":
                active_core_nonidle_cycles,
            "active_core_utilization":
                active_core_utilization,
            "aggregate_active_ipc":
                aggregate_active_ipc,
        },

        "cache": {
            "l3_accesses": l3_accesses,
            "l3_misses": l3_misses,
            "l3_accesses_per_kinst":
                per_kinst(l3_accesses, total_instructions),
            "l3_misses_per_kinst":
                per_kinst(l3_misses, total_instructions),
        },

        "memory": {
            "dram_reads": dram_reads,
            "dram_writes": dram_writes,
            "dram_accesses": dram_accesses,
            "dram_accesses_per_kinst":
                per_kinst(dram_accesses, total_instructions),

            # Retain provenance so we can audit aggregation.
            "controller_accesses": dram_controller_accesses,
        },

        # Populated by next bridge stage.
        "mcpat": {
            "core_w": None,
            "cache_w": None,
            "cpu_side_w": None,
        },

        # Populated when R6525 measurements arrive.
        "physical": {
            "cpu_power_w": None,
            "node_power_w": None,
        },

        "calibration": {
            "physical_calibrated": False,
        },
    }

    json.dump(
        record,
        sys.stdout,
        indent=2 if args.pretty else None,
        sort_keys=True,
    )
    print()


if __name__ == "__main__":
    main()
