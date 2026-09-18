#!/usr/bin/env python3

import json
import os
import sys
from collections import defaultdict


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNIPER_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../..")
)

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


def load_surrogate(power_config):
    model_path = os.path.join(
        SNIPER_ROOT,
        power_config["model_file"],
    )

    with open(model_path) as f:
        model = json.load(f)

    if model["model_id"] != "epyc7763_mcpat_cpu_surrogate_v1":
        raise RuntimeError(
            "Unexpected CPU power model: "
            f'{model["model_id"]}'
        )

    if model["target"]["physical_calibrated"]:
        raise RuntimeError(
            "Reference surrogate must not claim "
            "physical calibration"
        )

    return model


def evaluate_job_power(job, model):
    activity = job.get("activity")

    if not activity:
        raise RuntimeError(
            f'{job["job_id"]}: missing activity profile'
        )

    if activity.get("source") != "sniper-characterization":
        raise RuntimeError(
            f'{job["job_id"]}: unsupported activity source'
        )

    rate = float(activity["instruction_rate_gips"])

    domain = model["training_domain"]
    rate_min = float(
        domain["instruction_rate_gips_min"]
    )
    rate_max = float(
        domain["instruction_rate_gips_max"]
    )

    if not rate_min <= rate <= rate_max:
        raise RuntimeError(
            f'{job["job_id"]}: instruction rate '
            f'{rate} GIPS outside surrogate domain '
            f'[{rate_min}, {rate_max}]'
        )

    eq = model["equation"]

    power_w = (
        float(eq["intercept_w"])
        + float(
            eq["instruction_rate_gips_coefficient"]
        ) * rate
    )

    return {
        "job_id": job["job_id"],
        "instruction_rate_gips": rate,
        "power_per_node_w": power_w,
    }


def main():
    with open(WORKLOAD_PATH) as f:
        scenario = json.load(f)

    power_config = scenario.get("power", {})

    if power_config.get("model") != "mcpat-surrogate-v1":
        raise RuntimeError(
            "Timeline validator requires "
            "mcpat-surrogate-v1 backend"
        )

    model = load_surrogate(power_config)

    # Evaluate each job independently from its explicit
    # Sniper-derived activity profile.
    job_power = {}

    for job in scenario["jobs"]:
        job_power[job["job_id"]] = (
            evaluate_job_power(job, model)
        )

    # Each event carries a per-job node-count delta.
    #
    # This is intentionally different from the old validator,
    # which tracked only total running nodes and multiplied by
    # one fixed reference wattage.
    events = defaultdict(lambda: defaultdict(int))

    for job in scenario["jobs"]:
        job_id = job["job_id"]
        start = int(job["start_us"])
        end = start + int(job["duration_us"])
        nodes = int(job["num_nodes"])

        events[start][job_id] += nodes
        events[end][job_id] -= nodes

    times = sorted(events)

    running_by_job = defaultdict(int)
    intervals = []

    for i, time_us in enumerate(times):
        for job_id, delta in events[time_us].items():
            running_by_job[job_id] += delta

            if running_by_job[job_id] < 0:
                raise RuntimeError(
                    f"Negative running-node count for {job_id}"
                )

        if i + 1 >= len(times):
            continue

        next_time_us = times[i + 1]

        if next_time_us <= time_us:
            continue

        running_nodes = sum(running_by_job.values())

        # No numerical idle-node power is assumed.
        if running_nodes == 0:
            continue

        contributions = {}
        aggregate_power_w = 0.0

        for job_id, nodes in running_by_job.items():
            if nodes <= 0:
                continue

            per_node_w = (
                job_power[job_id]["power_per_node_w"]
            )

            contribution_w = nodes * per_node_w

            contributions[job_id] = {
                "nodes": nodes,
                "power_per_node_w": per_node_w,
                "aggregate_power_w": contribution_w,
            }

            aggregate_power_w += contribution_w

        duration_us = next_time_us - time_us

        # W * us -> J
        energy_j = (
            aggregate_power_w
            * duration_us
            * 1e-6
        )

        intervals.append({
            "start_us": time_us,
            "end_us": next_time_us,
            "running_nodes": running_nodes,
            "contributions": contributions,
            "aggregate_power_w": aggregate_power_w,
            "energy_j": energy_j,
        })

    print("=" * 78)
    print(
        "       SST CPU-CLUSTER SURROGATE POWER "
        "TIMELINE VALIDATION"
    )
    print("=" * 78)

    print(f"\nScenario: {scenario['id']}")
    print(f"Power model: {power_config['model']}")
    print(f"Model ID: {model['model_id']}")
    print("Status: REFERENCE_ONLY")
    print("Calibrated: False")

    print("\nJOB POWER ESTIMATES")

    for job in scenario["jobs"]:
        x = job_power[job["job_id"]]

        print(
            f"  {x['job_id']:<8} | "
            f"rate={x['instruction_rate_gips']:>8.3f} GIPS | "
            f"reference_power/node="
            f"{x['power_per_node_w']:>9.4f} W"
        )

    print("\nTIME-RESOLVED REFERENCE AGGREGATE")

    for x in intervals:
        print(
            f"  {x['start_us']:>4}-{x['end_us']:<4} us | "
            f"running_nodes={x['running_nodes']:>3} | "
            f"reference_power="
            f"{x['aggregate_power_w']:>9.2f} W | "
            f"reference_energy={x['energy_j']:.6f} J"
        )

        for job_id, c in sorted(
            x["contributions"].items()
        ):
            print(
                f"             {job_id:<8} "
                f"{c['nodes']:>3} nodes x "
                f"{c['power_per_node_w']:.4f} W "
                f"= {c['aggregate_power_w']:.2f} W"
            )

    print("\nVALIDATION")

    check(
        "Number of active intervals",
        len(intervals),
        3,
    )

    # Expected values are independently calculated from the
    # frozen model coefficients and scenario activity rates.
    eq = model["equation"]

    intercept = float(eq["intercept_w"])
    slope = float(
        eq["instruction_rate_gips_coefficient"]
    )

    expected_a = (
        intercept
        + slope * 25.187
    )

    expected_b = (
        intercept
        + slope * 12.732
    )

    expected = [
        (
            10,
            40,
            64,
            64 * expected_a,
        ),
        (
            40,
            110,
            80,
            64 * expected_a + 16 * expected_b,
        ),
        (
            110,
            160,
            16,
            16 * expected_b,
        ),
    ]

    for i, (start, end, nodes, watts) in enumerate(
        expected
    ):
        x = intervals[i]

        check(
            f"Interval {i + 1} start (us)",
            x["start_us"],
            start,
        )

        check(
            f"Interval {i + 1} end (us)",
            x["end_us"],
            end,
        )

        check(
            f"Interval {i + 1} running nodes",
            x["running_nodes"],
            nodes,
        )

        check(
            f"Interval {i + 1} reference power (W)",
            round(x["aggregate_power_w"], 2),
            round(watts, 2),
        )

    peak_nodes = max(
        x["running_nodes"]
        for x in intervals
    )

    peak_power = max(
        x["aggregate_power_w"]
        for x in intervals
    )

    total_energy = sum(
        x["energy_j"]
        for x in intervals
    )

    expected_energy = (
        (64 * expected_a) * 30e-6
        + (
            64 * expected_a
            + 16 * expected_b
        ) * 70e-6
        + (16 * expected_b) * 50e-6
    )

    check(
        "Peak running nodes",
        peak_nodes,
        80,
    )

    check(
        "Peak reference power (W)",
        round(peak_power, 2),
        round(
            64 * expected_a
            + 16 * expected_b,
            2,
        ),
    )

    check(
        "Total reference energy (J)",
        round(total_energy, 6),
        round(expected_energy, 6),
    )

    # Explicitly verify workload sensitivity.
    check(
        "Distinct per-job power estimates",
        round(expected_a, 6) != round(expected_b, 6),
        True,
    )

    print("\n" + "-" * 78)

    if failures:
        print(
            f"SURROGATE POWER TIMELINE: FAIL "
            f"({failures} error(s))"
        )
        return 1

    print("SURROGATE POWER TIMELINE: PASS")

    print(
        "Time-resolved cluster CPU-side aggregation validated "
        "using workload-sensitive Sniper-derived activity "
        "profiles and the frozen McPAT surrogate."
    )

    print(
        "These wattage and energy values are REFERENCE_ONLY "
        "and must not be interpreted as physically calibrated "
        "EPYC 7763 power predictions."
    )

    print(
        "Idle-node power is unavailable and is not included "
        "in the numerical aggregate."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
