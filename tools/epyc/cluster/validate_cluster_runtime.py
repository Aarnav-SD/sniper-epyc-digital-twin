#!/usr/bin/env python3

import sys

from build_cluster import build_cluster
from runtime import CpuCluster, Job


PASS = "[PASS]"
FAIL = "[FAIL]"

failures = 0


def check(label, actual, expected):
    global failures

    if actual == expected:
        print(f"  {PASS:<7} {label:<42} {actual}")
        return

    print(
        f"  {FAIL:<7} {label:<42} "
        f"actual={actual}, expected={expected}"
    )
    failures += 1


def main():
    nodes = build_cluster()
    cluster = CpuCluster(nodes)

    print("=" * 74)
    print("          HPC CPU COMPUTE-SUBSYSTEM RUNTIME VALIDATION")
    print("=" * 74)

    print("\nINITIAL STATE")

    check("Total CPU nodes", cluster.total_nodes, 420)
    check("Idle nodes", len(cluster.idle_nodes), 420)
    check("Running nodes", len(cluster.running_nodes), 0)
    check("Active cores", cluster.active_cores, 0)

    print("\nJOB A — FULL-NODE ALLOCATION")

    job_a = Job(
        job_id="job-A",
        num_nodes=64,
        cores_per_node=128,
        utilization=1.0,
    )

    allocated_a = cluster.allocate(job_a)

    check("Job A allocated nodes", len(allocated_a), 64)
    check("Job A first node", allocated_a[0].node_id, "CPU000")
    check("Job A last node", allocated_a[-1].node_id, "CPU063")

    check(
        "Job A active cores",
        sum(n.runtime.active_cores for n in allocated_a),
        8192
    )

    check("Cluster running nodes", len(cluster.running_nodes), 64)
    check("Cluster idle nodes", len(cluster.idle_nodes), 356)
    check("Cluster active cores", cluster.active_cores, 8192)

    print("\nJOB B — PARTIAL-NODE ALLOCATION")

    job_b = Job(
        job_id="job-B",
        num_nodes=16,
        cores_per_node=64,
        utilization=0.75,
    )

    allocated_b = cluster.allocate(job_b)

    check("Job B allocated nodes", len(allocated_b), 16)
    check("Job B first node", allocated_b[0].node_id, "CPU064")
    check("Job B last node", allocated_b[-1].node_id, "CPU079")

    check(
        "Job B active cores",
        sum(n.runtime.active_cores for n in allocated_b),
        1024
    )

    check("Total running nodes", len(cluster.running_nodes), 80)
    check("Remaining idle nodes", len(cluster.idle_nodes), 340)

    check(
        "Total active cores",
        cluster.active_cores,
        9216
    )

    print("\nJOB ISOLATION")

    check(
        "Nodes owned by Job A",
        len(cluster.nodes_for_job("job-A")),
        64
    )

    check(
        "Nodes owned by Job B",
        len(cluster.nodes_for_job("job-B")),
        16
    )

    overlap = (
        set(n.node_id for n in allocated_a)
        &
        set(n.node_id for n in allocated_b)
    )

    check("Job A/B node overlap", len(overlap), 0)

    print("\nRESOURCE EXHAUSTION")

    try:
        cluster.allocate(
            Job(
                job_id="too-large",
                num_nodes=341,
                cores_per_node=128,
            )
        )

        exhaustion_rejected = False

    except RuntimeError:
        exhaustion_rejected = True

    check(
        "Oversized allocation rejected",
        exhaustion_rejected,
        True
    )

    check(
        "State unchanged after rejection",
        len(cluster.running_nodes),
        80
    )

    print("\nJOB RELEASE")

    released_a = cluster.release("job-A")

    check("Released Job A nodes", released_a, 64)
    check("Job B remains allocated", len(cluster.running_nodes), 16)
    check("Idle nodes after Job A release", len(cluster.idle_nodes), 404)
    check("Active cores after Job A release", cluster.active_cores, 1024)

    released_b = cluster.release("job-B")

    check("Released Job B nodes", released_b, 16)
    check("Final running nodes", len(cluster.running_nodes), 0)
    check("Final idle nodes", len(cluster.idle_nodes), 420)
    check("Final active cores", cluster.active_cores, 0)

    print("\n" + "-" * 74)

    if failures:
        print(
            f"CPU COMPUTE-SUBSYSTEM RUNTIME: FAIL "
            f"({failures} error(s))"
        )
        return 1

    print("CPU COMPUTE-SUBSYSTEM RUNTIME: PASS")
    print(
        "Independent multi-node workload allocation validated "
        "across 420 CPU nodes."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
