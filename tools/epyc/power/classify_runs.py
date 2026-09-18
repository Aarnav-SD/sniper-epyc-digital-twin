#!/usr/bin/env python3

import argparse
import configparser
import json
from collections import Counter
from pathlib import Path


# These fields define the CPU/cache/base-memory architecture used by
# the power characterization model. NUMA topology is deliberately
# handled separately below.
POWER_BASELINE_FIELDS = [
    ("general", "total_cores"),

    ("perf_model/core", "frequency"),
    ("perf_model/core", "logical_cpus"),

    ("perf_model/cache", "levels"),

    ("perf_model/l1_icache", "cache_size"),
    ("perf_model/l1_icache", "associativity"),
    ("perf_model/l1_icache", "shared_cores"),

    ("perf_model/l1_dcache", "cache_size"),
    ("perf_model/l1_dcache", "associativity"),
    ("perf_model/l1_dcache", "shared_cores"),

    ("perf_model/l2_cache", "cache_size"),
    ("perf_model/l2_cache", "associativity"),
    ("perf_model/l2_cache", "shared_cores"),

    ("perf_model/l3_cache", "cache_size"),
    ("perf_model/l3_cache", "associativity"),
    ("perf_model/l3_cache", "shared_cores"),

    ("perf_model/dram", "num_controllers"),
    ("perf_model/dram", "controller_positions"),
    ("perf_model/dram", "type"),
    ("perf_model/dram", "latency"),
    ("perf_model/dram", "per_controller_bandwidth"),
    ("perf_model/dram", "controllers_interleaving"),
]


FINAL_NPS4_FIELDS = [
    ("perf_model/dram/numa", "enabled"),
    ("perf_model/dram/numa", "num_nodes"),
    ("perf_model/dram/numa", "cores_per_node"),
    ("perf_model/dram/numa", "nodes_per_socket"),
    ("perf_model/dram/numa", "same_socket_remote_latency_ns"),
    ("perf_model/dram/numa", "remote_socket_latency_ns"),

    ("perf_model/numa_reserve_thp", "num_numa_nodes"),
    ("perf_model/numa_reserve_thp", "kernel_size"),
]


def load_cfg(path):
    cfg = configparser.ConfigParser(
        interpolation=None,
        strict=False,
    )
    cfg.read(path)
    return cfg


def get(cfg, section, key):
    try:
        return cfg.get(section, key)
    except (configparser.NoSectionError,
            configparser.NoOptionError):
        return "<MISSING>"


def compare(cfg, reference, fields):
    differences = []

    for section, key in fields:
        expected = get(reference, section, key)
        actual = get(cfg, section, key)

        if actual != expected:
            differences.append({
                "field": f"{section}/{key}",
                "expected": expected,
                "actual": actual,
            })

    return differences


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path.home() / "sniper-runs" / "epyc7763",
    )

    parser.add_argument(
        "--reference",
        default="numa-lat-2-nps4-1789400190",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    cfg_paths = []

    for p in sorted(args.run_root.rglob("sim.cfg")):
        simdir = p.parent

        if (
            (simdir / "sim.stats.sqlite3").exists()
            or (simdir / "sim.stats").exists()
        ):
            cfg_paths.append(p)

    reference_paths = [
        p for p in cfg_paths
        if p.parent.parent.name == args.reference
    ]

    if len(reference_paths) != 1:
        raise SystemExit(
            f"Expected exactly one reference run, "
            f"found {len(reference_paths)}"
        )

    reference = load_cfg(reference_paths[0])

    records = []

    for cfg_path in cfg_paths:
        cfg = load_cfg(cfg_path)

        baseline_diff = compare(
            cfg,
            reference,
            POWER_BASELINE_FIELDS,
        )

        nps4_diff = compare(
            cfg,
            reference,
            FINAL_NPS4_FIELDS,
        )

        power_baseline_compatible = not baseline_diff
        final_nps4_compatible = (
            power_baseline_compatible
            and not nps4_diff
        )

        if final_nps4_compatible:
            tier = "FINAL_NPS4"
        elif power_baseline_compatible:
            tier = "POWER_BASELINE"
        else:
            tier = "INCOMPATIBLE"

        records.append({
            "run": cfg_path.parent.parent.name,
            "results_dir": str(cfg_path.parent),
            "tier": tier,
            "power_baseline_compatible":
                power_baseline_compatible,
            "final_nps4_compatible":
                final_nps4_compatible,
            "baseline_differences": baseline_diff,
            "nps4_differences": nps4_diff,
        })

    counts = Counter(r["tier"] for r in records)

    print("=== RUN COMPATIBILITY ===")
    print("completed runs :", len(records))
    print("FINAL_NPS4     :", counts["FINAL_NPS4"])
    print("POWER_BASELINE :", counts["POWER_BASELINE"])
    print("INCOMPATIBLE   :", counts["INCOMPATIBLE"])

    print("\n=== FINAL_NPS4 ===")
    for r in records:
        if r["tier"] == "FINAL_NPS4":
            print(" ", r["run"])

    print("\n=== POWER_BASELINE SAMPLE ===")
    baseline = [
        r for r in records
        if r["tier"] == "POWER_BASELINE"
    ]

    for r in baseline[:30]:
        print(" ", r["run"])

    if len(baseline) > 30:
        print(f"  ... +{len(baseline) - 30} more")

    print("\n=== INCOMPATIBLE ===")
    for r in records:
        if r["tier"] == "INCOMPATIBLE":
            print(
                f"  {r['run']} "
                f"({len(r['baseline_differences'])} "
                f"baseline differences)"
            )

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "schema_version": 1,
            "reference_run": args.reference,
            "counts": dict(counts),
            "runs": records,
        }

        with args.output.open("w") as f:
            json.dump(
                payload,
                f,
                indent=2,
                sort_keys=True,
            )
            f.write("\n")

        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
