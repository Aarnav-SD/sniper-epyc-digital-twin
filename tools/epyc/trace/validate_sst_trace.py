#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


CHECKPOINTS = [
    {
        "time_us": 0,
        "running_nodes": 0,
        "active_cores": 0,
        "reference_power_w": 0.0,
        "active_jobs": [],
    },
    {
        "time_us": 10,
        "running_nodes": 64,
        "active_cores": 8192,
        "reference_power_w": 6468.352,
        "active_jobs": ["JOB_A"],
    },
    {
        "time_us": 40,
        "running_nodes": 80,
        "active_cores": 9216,
        "reference_power_w": 7989.9872,
        "active_jobs": ["JOB_A", "JOB_B"],
    },
    {
        "time_us": 110,
        "running_nodes": 16,
        "active_cores": 1024,
        "reference_power_w": 1521.6352,
        "active_jobs": ["JOB_B"],
    },
    {
        "time_us": 160,
        "running_nodes": 0,
        "active_cores": 0,
        "reference_power_w": 0.0,
        "active_jobs": [],
    },
]


def load_trace(path):
    return json.loads(Path(path).read_text())


def validate_structure(trace):
    assert trace["schema_version"] == 1
    assert trace["trace_type"] == "sst_epyc_cpu_runtime"

    nodes = trace["nodes"]
    events = trace["events"]

    assert len(nodes) == 420
    assert len(events) == 160

    indices = [node["index"] for node in nodes]
    assert indices == list(range(420))

    physical_ids = [
        node["physical_id"]
        for node in nodes
    ]

    assert len(set(physical_ids)) == 420

    starts = [
        event
        for event in events
        if event["type"] == "JOB_START"
    ]

    ends = [
        event
        for event in events
        if event["type"] == "JOB_END"
    ]

    assert len(starts) == 80
    assert len(ends) == 80

    start_keys = {
        (
            event["job_id"],
            event["node_index"],
        )
        for event in starts
    }

    end_keys = {
        (
            event["job_id"],
            event["node_index"],
        )
        for event in ends
    }

    assert start_keys == end_keys

    for event in starts:
        assert event["power_status"] == "REFERENCE_ONLY"
        assert event["physical_calibrated"] is False
        assert event["reference_power_w"] > 0
        assert event["active_cores"] > 0
        assert event["instruction_rate_gips"] is not None
        assert event["activity_source"] is not None
        assert event["activity_profile"] is not None


def reconstruct_state(trace, time_us):
    running = {}

    for event in trace["events"]:
        if event["time_us"] > time_us:
            break

        key = (
            event["job_id"],
            event["node_index"],
        )

        if event["type"] == "JOB_START":
            running[key] = event

        elif event["type"] == "JOB_END":
            running.pop(key, None)

    running_events = list(running.values())

    return {
        "running_nodes": len(running_events),
        "active_cores": sum(
            event["active_cores"]
            for event in running_events
        ),
        "reference_power_w": sum(
            event["reference_power_w"]
            for event in running_events
        ),
        "active_jobs": sorted({
            event["job_id"]
            for event in running_events
        }),
    }


def build_power_timeline(trace):
    boundaries = sorted({
        0.0,
        trace["scenario"]["duration_us"],
        *[
            event["time_us"]
            for event in trace["events"]
        ],
    })

    segments = []

    for start_us, end_us in zip(
        boundaries,
        boundaries[1:],
    ):
        state = reconstruct_state(
            trace,
            start_us,
        )

        segments.append({
            "start_us": start_us,
            "end_us": end_us,
            **state,
        })

    return segments


def active_energy_j(trace):
    energy_j = 0.0

    for segment in build_power_timeline(trace):
        duration_s = (
            segment["end_us"]
            - segment["start_us"]
        ) * 1e-6

        energy_j += (
            segment["reference_power_w"]
            * duration_s
        )

    return energy_j


def validate_checkpoints(trace):
    failures = 0

    print("RUNTIME CHECKPOINTS")

    for expected in CHECKPOINTS:
        t = expected["time_us"]
        actual = reconstruct_state(trace, t)

        nodes_ok = (
            actual["running_nodes"]
            == expected["running_nodes"]
        )

        cores_ok = (
            actual["active_cores"]
            == expected["active_cores"]
        )

        power_ok = abs(
            actual["reference_power_w"]
            - expected["reference_power_w"]
        ) < 1e-6

        jobs_ok = (
            actual["active_jobs"]
            == expected["active_jobs"]
        )

        passed = (
            nodes_ok
            and cores_ok
            and power_ok
            and jobs_ok
        )

        if not passed:
            failures += 1

        jobs = (
            ",".join(actual["active_jobs"])
            if actual["active_jobs"]
            else "-"
        )

        print(
            f"{'PASS' if passed else 'FAIL'} "
            f"t={t:g}us "
            f"nodes={actual['running_nodes']} "
            f"cores={actual['active_cores']} "
            f"power={actual['reference_power_w']:.4f}W "
            f"jobs={jobs}"
        )

    return failures


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Validate an SST EPYC CPU runtime trace."
        )
    )

    parser.add_argument(
        "trace",
        help="Trace JSON to validate",
    )

    args = parser.parse_args()

    trace = load_trace(args.trace)

    print("SST TRACE VALIDATION")
    print("=" * 60)

    try:
        validate_structure(trace)
        print("PASS trace structure")
    except AssertionError:
        print("FAIL trace structure")
        raise

    print()

    failures = validate_checkpoints(trace)

    print()
    print("POWER TIMELINE")

    timeline = build_power_timeline(trace)

    for segment in timeline:
        jobs = (
            ",".join(segment["active_jobs"])
            if segment["active_jobs"]
            else "-"
        )

        print(
            f"{segment['start_us']:g}-"
            f"{segment['end_us']:g}us "
            f"nodes={segment['running_nodes']} "
            f"cores={segment['active_cores']} "
            f"power="
            f"{segment['reference_power_w']:.4f}W "
            f"jobs={jobs}"
        )

    energy = active_energy_j(trace)

    # This expected value is based on the precision
    # actually emitted by SST:
    #
    # JOB_A:
    #   64 * 101.068 W * 100 us
    #
    # JOB_B:
    #   16 * 95.1022 W * 120 us
    #
    expected_energy_j = 0.829431424

    energy_ok = abs(
        energy - expected_energy_j
    ) < 1e-9

    print()
    print(
        f"{'PASS' if energy_ok else 'FAIL'} "
        f"active reference energy="
        f"{energy:.9f} J"
    )

    if not energy_ok:
        failures += 1

    print()

    if failures:
        print(
            f"SST TRACE VALIDATION: FAIL "
            f"({failures} checks failed)"
        )
        raise SystemExit(1)

    print("SST TRACE VALIDATION: PASS")


if __name__ == "__main__":
    main()
