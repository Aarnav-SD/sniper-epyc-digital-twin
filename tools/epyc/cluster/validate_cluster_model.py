#!/usr/bin/env python3

import sys
from collections import Counter, defaultdict

from build_cluster import build_cluster


PASS = "[PASS]"
FAIL = "[FAIL]"

failures = 0


def check(label, actual, expected):
    global failures

    if actual == expected:
        print(f"  {PASS:<7} {label:<40} {actual}")
        return

    print(
        f"  {FAIL:<7} {label:<40} "
        f"actual={actual}, expected={expected}"
    )
    failures += 1


def main():
    nodes = build_cluster()

    print("=" * 72)
    print("          HPC CPU COMPUTE-SUBSYSTEM MODEL VALIDATION")
    print("=" * 72)

    print("\nCLUSTER INSTANTIATION")

    check("Compute-node objects", len(nodes), 420)

    check(
        "Unique node IDs",
        len({n.node_id for n in nodes}),
        420
    )

    check(
        "Unique global indices",
        len({n.global_index for n in nodes}),
        420
    )

    check("First node ID", nodes[0].node_id, "CPU000")
    check("Last node ID", nodes[-1].node_id, "CPU419")

    print("\nRACK PLACEMENT")

    rack_counts = Counter(n.rack_id for n in nodes)
    rack_types = defaultdict(set)

    for node in nodes:
        rack_types[node.rack_id].add(node.rack_type)

    check("Total racks represented", len(rack_counts), 13)

    regular_racks = [
        rack for rack in rack_counts
        if "regular" in rack_types[rack]
    ]

    special_racks = [
        rack for rack in rack_counts
        if "special" in rack_types[rack]
    ]

    check("Regular racks represented", len(regular_racks), 11)
    check("Special racks represented", len(special_racks), 2)

    regular_counts_ok = all(
        rack_counts[rack] == 38
        for rack in regular_racks
    )

    check(
        "38 CPU nodes / regular rack",
        regular_counts_ok,
        True
    )

    special_counts_ok = all(
        rack_counts[rack] == 1
        for rack in special_racks
    )

    check(
        "1 CPU node / special rack",
        special_counts_ok,
        True
    )

    print("\nHARDWARE EXPANSION")

    total_cores = sum(
        n.hardware.total_cores
        for n in nodes
    )

    total_memory_gib = sum(
        n.hardware.memory_gib
        for n in nodes
    )

    total_numa = sum(
        n.hardware.numa_nodes
        for n in nodes
    )

    total_l3 = sum(
        n.hardware.l3_groups
        for n in nodes
    )

    total_dram_controllers = sum(
        n.hardware.dram_controllers
        for n in nodes
    )

    check("Physical CPU cores", total_cores, 53760)
    check("NUMA domains", total_numa, 3360)
    check("L3 groups", total_l3, 6720)
    check("DRAM controllers", total_dram_controllers, 6720)

    # 420 × 512 GiB
    check("Aggregate CPU-node memory (GiB)", total_memory_gib, 215040)

    print("\nINITIAL RUNTIME STATE")

    idle_nodes = sum(n.is_idle for n in nodes)

    check("Idle nodes", idle_nodes, 420)

    check(
        "Nodes with active jobs",
        sum(n.runtime.job_id is not None for n in nodes),
        0
    )

    check(
        "Initial active cores",
        sum(n.runtime.active_cores for n in nodes),
        0
    )

    print("\nNODE INDEPENDENCE TEST")

    nodes[0].assign_job(
        job_id="validation-job",
        active_cores=128,
        utilization=1.0
    )

    check(
        "CPU000 active cores",
        nodes[0].runtime.active_cores,
        128
    )

    check(
        "CPU000 job",
        nodes[0].runtime.job_id,
        "validation-job"
    )

    check(
        "CPU001 remains idle",
        nodes[1].is_idle,
        True
    )

    check(
        "Other 419 nodes remain idle",
        sum(n.is_idle for n in nodes[1:]),
        419
    )

    nodes[0].release_job()

    check(
        "CPU000 returns to idle",
        nodes[0].is_idle,
        True
    )

    print("\n" + "-" * 72)

    if failures:
        print(
            f"CPU COMPUTE-SUBSYSTEM MODEL: FAIL "
            f"({failures} error(s))"
        )
        return 1

    print("CPU COMPUTE-SUBSYSTEM MODEL: PASS")
    print("420 independently addressable CPU compute nodes instantiated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
