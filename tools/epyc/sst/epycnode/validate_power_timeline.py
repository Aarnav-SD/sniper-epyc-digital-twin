#!/usr/bin/env python3

import json
import os
import sys
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNIPER_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))

WORKLOAD_PATH = os.path.join(
    SNIPER_ROOT,
    "configs/workloads/sst_multijob_validation.json",
)

PASS = "[PASS]"
FAIL = "[FAIL]"

failures = 0


def check(label, actual, expected):
    global failures

    if actual == expected:
        print(f"  {PASS:<7} {label:<42} {actual}")
    else:
        print(
            f"  {FAIL:<7} {label:<42} "
            f"actual={actual}, expected={expected}"
        )
        failures += 1


def main():
    with open(WORKLOAD_PATH) as f:
        scenario = json.load(f)

    power = scenario.get("power", {})

    if power.get("model") != "mcpat-reference":
        raise RuntimeError(
            "Timeline validator requires mcpat-reference backend"
        )

    reference_power_w = float(power["reference_power_w"])

    # Each job contributes +num_nodes at start and -num_nodes at end.
    events = defaultdict(int)

    for job in scenario["jobs"]:
        start = int(job["start_us"])
        end = start + int(job["duration_us"])
        nodes = int(job["num_nodes"])

        events[start] += nodes
        events[end] -= nodes

    times = sorted(events)

    running_nodes = 0
    intervals = []

    for i, time_us in enumerate(times):
        running_nodes += events[time_us]

        if i + 1 >= len(times):
            continue

        next_time_us = times[i + 1]

        if next_time_us <= time_us:
            continue

        aggregate_power_w = running_nodes * reference_power_w
        duration_us = next_time_us - time_us

        # W * us -> J
        energy_j = aggregate_power_w * duration_us * 1e-6

        intervals.append({
            "start_us": time_us,
            "end_us": next_time_us,
            "running_nodes": running_nodes,
            "aggregate_power_w": aggregate_power_w,
            "energy_j": energy_j,
        })

    print("=" * 78)
    print("       SST CPU-CLUSTER REFERENCE POWER TIMELINE VALIDATION")
    print("=" * 78)

    print(f"\nScenario: {scenario['id']}")
    print("Power model: mcpat-reference")
    print(f"Reference power/node: {reference_power_w:.2f} W")
    print("Status: REFERENCE_ONLY")
    print("Calibrated: False")

    print("\nTIME-RESOLVED REFERENCE AGGREGATE")

    for x in intervals:
        print(
            f"  {x['start_us']:>4}-{x['end_us']:<4} us | "
            f"running_nodes={x['running_nodes']:>3} | "
            f"reference_power={x['aggregate_power_w']:>8.2f} W | "
            f"reference_energy={x['energy_j']:.6f} J"
        )

    print("\nVALIDATION")

    expected = [
        (10, 40, 64, 5662.72),
        (40, 110, 80, 7078.40),
        (110, 160, 16, 1415.68),
    ]

    check("Number of active intervals", len(intervals), 3)

    for i, (start, end, nodes, watts) in enumerate(expected):
        x = intervals[i]

        check(f"Interval {i + 1} start (us)", x["start_us"], start)
        check(f"Interval {i + 1} end (us)", x["end_us"], end)
        check(f"Interval {i + 1} running nodes",
              x["running_nodes"], nodes)
        check(
            f"Interval {i + 1} reference power (W)",
            round(x["aggregate_power_w"], 2),
            watts,
        )

    peak_nodes = max(x["running_nodes"] for x in intervals)
    peak_power = max(x["aggregate_power_w"] for x in intervals)
    total_energy = sum(x["energy_j"] for x in intervals)

    check("Peak running nodes", peak_nodes, 80)
    check("Peak reference power (W)",
          round(peak_power, 2), 7078.40)

    # Analytic expected diagnostic energy:
    # 5662.72*30us + 7078.40*70us + 1415.68*50us
    expected_energy = (
        5662.72 * 30e-6
        + 7078.40 * 70e-6
        + 1415.68 * 50e-6
    )

    check(
        "Total reference energy (J)",
        round(total_energy, 6),
        round(expected_energy, 6),
    )

    print("\n" + "-" * 78)

    if failures:
        print(
            f"REFERENCE POWER TIMELINE: FAIL "
            f"({failures} error(s))"
        )
        return 1

    print("REFERENCE POWER TIMELINE: PASS")
    print(
        "Time-resolved cluster aggregation validated using the "
        "uncalibrated McPAT diagnostic reference backend."
    )
    print(
        "These wattage and energy values are REFERENCE_ONLY and "
        "must not be interpreted as physical EPYC 7763 predictions."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
