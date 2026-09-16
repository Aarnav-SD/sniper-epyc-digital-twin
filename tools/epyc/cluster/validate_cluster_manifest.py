#!/usr/bin/env python3

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

NODE_MANIFEST = ROOT / "configs/hardware/r6525_epyc7763.json"
CLUSTER_MANIFEST = ROOT / "configs/cluster/internship_hpc.json"


PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"


failures = 0


def check(label, actual, expected):
    global failures

    if actual == expected:
        print(f"  {PASS:<7} {label:<36} {actual}")
        return True

    print(
        f"  {FAIL:<7} {label:<36} "
        f"actual={actual}, expected={expected}"
    )
    failures += 1
    return False


def load_json(path):
    if not path.exists():
        print(f"{FAIL} Missing manifest: {path}")
        sys.exit(1)

    with path.open() as f:
        return json.load(f)


def main():
    node = load_json(NODE_MANIFEST)
    cluster = load_json(CLUSTER_MANIFEST)

    print("=" * 68)
    print("        HPC CPU COMPUTE-SUBSYSTEM MANIFEST VALIDATION")
    print("=" * 68)

    print("\nREFERENCE CPU NODE")
    print(
        f"  {node['platform']['vendor']} "
        f"{node['platform']['model']}"
    )
    print(f"  CPU: {node['cpu']['model']}")

    check(
        "Sockets per node",
        node["cpu"]["sockets"],
        2
    )

    check(
        "Cores per socket",
        node["cpu"]["cores_per_socket"],
        64
    )

    check(
        "Physical cores per node",
        node["cpu"]["total_physical_cores"],
        128
    )

    check(
        "NUMA domains per node",
        node["numa"]["total_nodes"],
        8
    )

    check(
        "Cores per NUMA domain",
        node["numa"]["cores_per_node"],
        16
    )

    check(
        "L3 groups per node",
        node["cache"]["l3_groups"],
        16
    )

    check(
        "DRAM controllers per node",
        node["memory"]["controllers"],
        16
    )

    print("\nCLUSTER COMPOSITION")

    regular = cluster["racks"]["regular"]
    special = cluster["racks"]["special"]

    regular_cpu_nodes = (
        regular["count"] *
        regular["cpu_nodes_per_rack"]
    )

    special_cpu_nodes = (
        special["count"] *
        special["cpu_nodes_per_rack"]
    )

    calculated_cpu_nodes = regular_cpu_nodes + special_cpu_nodes
    declared_cpu_nodes = cluster["cpu_compute"]["total_nodes"]

    check(
        "Regular racks",
        regular["count"],
        11
    )

    check(
        "CPU nodes / regular rack",
        regular["cpu_nodes_per_rack"],
        38
    )

    check(
        "CPU nodes in regular racks",
        regular_cpu_nodes,
        418
    )

    check(
        "Special racks",
        special["count"],
        2
    )

    check(
        "CPU nodes in special racks",
        special_cpu_nodes,
        2
    )

    check(
        "Calculated CPU node count",
        calculated_cpu_nodes,
        420
    )

    check(
        "Declared CPU node count",
        declared_cpu_nodes,
        calculated_cpu_nodes
    )

    check(
        "CPU node type",
        cluster["cpu_compute"]["node_type"],
        node["id"]
    )

    cores_per_node = node["cpu"]["total_physical_cores"]

    total_cpu_cores = declared_cpu_nodes * cores_per_node

    print("\nDERIVED CPU COMPUTE SUBSYSTEM")

    check(
        "CPU compute nodes",
        declared_cpu_nodes,
        420
    )

    check(
        "Physical CPU cores",
        total_cpu_cores,
        53760
    )

    total_numa_domains = (
        declared_cpu_nodes *
        node["numa"]["total_nodes"]
    )

    total_l3_groups = (
        declared_cpu_nodes *
        node["cache"]["l3_groups"]
    )

    total_dram_controllers = (
        declared_cpu_nodes *
        node["memory"]["controllers"]
    )

    print(f"  {INFO:<7} NUMA domains across CPU nodes       {total_numa_domains}")
    print(f"  {INFO:<7} L3 groups across CPU nodes          {total_l3_groups}")
    print(f"  {INFO:<7} DRAM controllers across CPU nodes   {total_dram_controllers}")

    print("\nOUT-OF-SCOPE SUBSYSTEMS")

    print(
        f"  GPU nodes       : "
        f"{cluster['gpu_compute']['total_nodes']} "
        f"({cluster['gpu_compute']['model_status']})"
    )

    print(
        f"  Network         : "
        f"{cluster['network']['type']} "
        f"({cluster['network']['model_status']})"
    )

    print(
        f"  Storage         : "
        f"{cluster['storage']['type']} "
        f"({cluster['storage']['model_status']})"
    )

    print(
        f"  Scheduler       : "
        f"{cluster['scheduler']['type']} "
        f"({cluster['scheduler']['model_status']})"
    )

    print("\n" + "-" * 68)

    if failures:
        print(f"CLUSTER MANIFEST VALIDATION: FAIL ({failures} error(s))")
        return 1

    print("CLUSTER MANIFEST VALIDATION: PASS")
    print(
        "420 CPU nodes / 53,760 physical cores represented."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
