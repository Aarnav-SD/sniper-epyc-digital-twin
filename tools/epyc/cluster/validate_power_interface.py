#!/usr/bin/env python3

import sys

from build_cluster import build_cluster
from runtime import CpuCluster, Job
from power import (
    PendingCalibrationPowerModel,
    FixedMcPATReferenceModel,
)


PASS = "[PASS]"
FAIL = "[FAIL]"

failures = 0


def check(label, actual, expected):
    global failures

    if actual == expected:
        print(f"  {PASS:<7} {label:<44} {actual}")
        return

    print(
        f"  {FAIL:<7} {label:<44} "
        f"actual={actual}, expected={expected}"
    )
    failures += 1


def main():

    cluster = CpuCluster(build_cluster())

    cluster.allocate(
        Job(
            job_id="power-test",
            num_nodes=4,
            cores_per_node=128,
            utilization=1.0,
        )
    )

    print("=" * 76)
    print("            HPC CPU POWER-MODEL INTERFACE VALIDATION")
    print("=" * 76)

    print("\nCALIBRATION-SAFE BACKEND")

    pending = PendingCalibrationPowerModel()
    result = cluster.estimate_power(pending)

    check("Running nodes", result["running_nodes"], 4)
    check("Nodes with numerical power", result["nodes_with_power"], 0)
    check("Aggregate available", result["complete"], False)
    check("Aggregate power", result["aggregate_power_w"], None)
    check("Calibrated", result["calibrated"], False)

    check(
        "CPU000 status",
        result["per_node"]["CPU000"].status,
        "PENDING"
    )

    print("\nRAW McPAT REFERENCE BACKEND")

    reference = FixedMcPATReferenceModel(
        reference_power_w=88.48
    )

    result = cluster.estimate_power(reference)

    check("Running nodes", result["running_nodes"], 4)
    check("Nodes with reference power", result["nodes_with_power"], 4)
    check("Reference aggregate available", result["complete"], True)

    check(
        "Reference aggregate power (W)",
        round(result["aggregate_power_w"], 2),
        353.92
    )

    check("Reference model calibrated", result["calibrated"], False)

    check(
        "CPU000 reference power (W)",
        result["per_node"]["CPU000"].power_w,
        88.48
    )

    check(
        "CPU000 reference status",
        result["per_node"]["CPU000"].status,
        "REFERENCE_ONLY"
    )

    print("\nIDLE-NODE BEHAVIOR")

    check(
        "CPU004 remains idle",
        cluster.nodes[4].is_idle,
        True
    )

    check(
        "CPU004 has no reference wattage",
        result["per_node"]["CPU004"].power_w,
        None
    )

    print("\nSAFETY CHECK")

    # The diagnostic backend may produce a numerical aggregate, but it must
    # never claim that the result is physically calibrated.
    unsafe_claim = (
        result["aggregate_power_w"] is not None
        and result["calibrated"]
    )

    check(
        "Uncalibrated aggregate not marked calibrated",
        unsafe_claim,
        False
    )

    print("\n" + "-" * 76)

    if failures:
        print(
            f"POWER-MODEL INTERFACE: FAIL "
            f"({failures} error(s))"
        )
        return 1

    print("POWER-MODEL INTERFACE: PASS")
    print(
        "Cluster power plumbing validated without claiming "
        "uncalibrated McPAT values as physical EPYC power."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
