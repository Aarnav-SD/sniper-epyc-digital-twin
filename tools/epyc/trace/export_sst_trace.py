#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


INIT_RE = re.compile(
    r"^\[(?P<sst_id>CPU\d+)\]\s+initialized$"
)

RACK_RE = re.compile(
    r"^\[(?P<sst_id>CPU\d+)\]\s+"
    r"rack=(?P<rack>R\d+)\s+"
    r"rack_type=(?P<rack_type>[A-Za-z0-9_-]+)$"
)

RUN_RE = re.compile(
    r"^\[(?P<sst_id>CPU\d+)\]\s+"
    r"t=(?P<time>[0-9.]+)us\s+"
    r"state=RUNNING\s+"
    r"job=(?P<job>[A-Za-z0-9_-]+)\s+"
    r"active_cores=(?P<cores>\d+)\s+"
    r"utilization=(?P<util>[0-9.]+)$"
)

POWER_RE = re.compile(
    r"^\[(?P<sst_id>CPU\d+)\]\s+"
    r"t=(?P<time>[0-9.]+)us\s+"
    r"power_model=(?P<power_model>[A-Za-z0-9_.-]+)\s+"
    r"power_w=(?P<power>[0-9.]+)\s+"
    r"status=(?P<status>[A-Za-z0-9_-]+)\s+"
    r"calibrated=(?P<calibrated>true|false)$"
)

COMPLETE_RE = re.compile(
    r"^\[(?P<sst_id>CPU\d+)\]\s+"
    r"t=(?P<time>[0-9.]+)us\s+"
    r"state=IDLE\s+"
    r"job=(?P<job>[A-Za-z0-9_-]+)\s+"
    r"completed$"
)


def cpu_index(sst_id):
    return int(sst_id[3:])


def physical_id(index):
    if index < 418:
        rack = index // 38
        rack_node = index % 38 + 1
    elif index == 418:
        rack = 11
        rack_node = 1
    elif index == 419:
        rack = 12
        rack_node = 1
    else:
        raise ValueError(f"Invalid CPU node index: {index}")

    return f"r{rack:02d}cn{rack_node:02d}"


def physical_location(index):
    if index < 418:
        rack = index // 38
        rack_node = index % 38 + 1
        rack_type = "regular"
    elif index == 418:
        rack = 11
        rack_node = 1
        rack_type = "special"
    elif index == 419:
        rack = 12
        rack_node = 1
        rack_type = "special"
    else:
        raise ValueError(f"Invalid CPU node index: {index}")

    return {
        "physical_id": f"r{rack:02d}cn{rack_node:02d}",
        "rack_id": f"R{rack:02d}",
        "rack_node": rack_node,
        "rack_type": rack_type,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export SST EpycNode runtime output as trace schema v1."
    )

    parser.add_argument(
        "--log",
        required=True,
        help="SST stdout/stderr log",
    )

    parser.add_argument(
        "--workload",
        required=True,
        help="Workload JSON used for the SST run",
    )

    parser.add_argument(
        "--power-model",
        required=True,
        help="Reduced-order CPU power model JSON",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output trace JSON",
    )

    args = parser.parse_args()

    log_path = Path(args.log)
    workload_path = Path(args.workload)
    model_path = Path(args.power_model)
    output_path = Path(args.output)

    workload = json.loads(workload_path.read_text())
    model = json.loads(model_path.read_text())

    lines = log_path.read_text().splitlines()

    initialized_ids = set()
    rack_metadata = {}
    running_by_key = {}
    power_by_key = {}
    completion_events = []

    for line in lines:
        line = line.strip()

        match = INIT_RE.match(line)

        if match:
            initialized_ids.add(
                match.group("sst_id")
            )
            continue

        match = RACK_RE.match(line)

        if match:
            rack_metadata[
                match.group("sst_id")
            ] = {
                "rack_id": match.group("rack"),
                "rack_type": match.group(
                    "rack_type"
                ),
            }
            continue

        match = RUN_RE.match(line)

        if match:
            sst_id = match.group("sst_id")
            time_us = float(match.group("time"))
            job_id = match.group("job")

            key = (sst_id, time_us)

            running_by_key[key] = {
                "time_us": time_us,
                "type": "JOB_START",
                "job_id": job_id,
                "node_index": cpu_index(sst_id),
                "sst_id": sst_id,
                "physical_id": physical_id(
                    cpu_index(sst_id)
                ),
                "active_cores": int(
                    match.group("cores")
                ),
                "utilization": float(
                    match.group("util")
                ),
            }
            continue

        match = POWER_RE.match(line)

        if match:
            sst_id = match.group("sst_id")
            time_us = float(match.group("time"))

            key = (sst_id, time_us)

            power_by_key[key] = {
                "power_model":
                    match.group("power_model"),
                "reference_power_w":
                    float(match.group("power")),
                "power_status":
                    match.group("status"),
                "physical_calibrated":
                    match.group("calibrated")
                    == "true",
            }
            continue

        match = COMPLETE_RE.match(line)

        if match:
            sst_id = match.group("sst_id")

            completion_events.append({
                "time_us": float(
                    match.group("time")
                ),
                "type": "JOB_END",
                "job_id": match.group("job"),
                "node_index":
                    cpu_index(sst_id),
                "sst_id": sst_id,
                "physical_id":
                    physical_id(
                        cpu_index(sst_id)
                    ),
            })

    if len(initialized_ids) != 420:
        raise RuntimeError(
            "Expected 420 initialized nodes, "
            f"found {len(initialized_ids)}"
        )

    if len(rack_metadata) != 420:
        raise RuntimeError(
            "Expected rack metadata for 420 nodes, "
            f"found {len(rack_metadata)}"
        )

    initialized = {}

    for sst_id in initialized_ids:
        index = cpu_index(sst_id)
        location = physical_location(index)

        logged = rack_metadata[sst_id]

        if logged["rack_id"] != location["rack_id"]:
            raise RuntimeError(
                f"{sst_id}: SST rack "
                f"{logged['rack_id']} != derived rack "
                f"{location['rack_id']}"
            )

        if (
            logged["rack_type"]
            != location["rack_type"]
        ):
            raise RuntimeError(
                f"{sst_id}: SST rack type "
                f"{logged['rack_type']} != derived "
                f"{location['rack_type']}"
            )

        initialized[sst_id] = {
            "index": index,
            "sst_id": sst_id,
            **location,
        }

    if len(initialized) != 420:
        raise RuntimeError(
            f"Expected 420 initialized nodes, found {len(initialized)}"
        )

    if len(running_by_key) != 80:
        raise RuntimeError(
            "Expected 80 RUNNING events, "
            f"found {len(running_by_key)}"
        )

    if len(power_by_key) != 80:
        raise RuntimeError(
            "Expected 80 power reports, "
            f"found {len(power_by_key)}"
        )

    if len(completion_events) != 80:
        raise RuntimeError(
            "Expected 80 completion events, "
            f"found {len(completion_events)}"
        )

    running_keys = set(running_by_key)
    power_keys = set(power_by_key)

    if running_keys != power_keys:
        missing_power = (
            running_keys - power_keys
        )
        orphan_power = (
            power_keys - running_keys
        )

        raise RuntimeError(
            "Runtime/power event mismatch. "
            f"missing_power={sorted(missing_power)} "
            f"orphan_power={sorted(orphan_power)}"
        )

    running_events = []

    for key in sorted(
        running_by_key,
        key=lambda item: (
            item[1],
            cpu_index(item[0]),
        ),
    ):
        event = running_by_key[key].copy()
        event.update(power_by_key[key])
        running_events.append(event)

    if not completion_events:
        raise RuntimeError("No completion events found in SST log")

    # Add characterization metadata from the workload manifest.
    workload_jobs = {
        job["job_id"]: job
        for job in workload["jobs"]
    }

    for event in running_events:
        job = workload_jobs[event["job_id"]]

        activity = job.get("activity", {})

        event["instruction_rate_gips"] = (
            activity.get("instruction_rate_gips")
        )

        event["activity_source"] = (
            activity.get("source")
        )

        event["activity_profile"] = (
            activity.get("profile")
        )

    events = sorted(
        running_events + completion_events,
        key=lambda event: (
            event["time_us"],
            0 if event["type"] == "JOB_END" else 1,
            event["node_index"],
        ),
    )

    duration_us = max(
        event["time_us"]
        for event in completion_events
    )

    trace = {
        "schema_version": 1,
        "trace_type": "sst_epyc_cpu_runtime",
        "source": {
            "simulator": "SST",
            "runtime_model": "EpycNode",
            "workload_file": workload_path.name,
        },
        "scenario": {
            "id": workload.get(
                "scenario_id",
                workload_path.stem,
            ),
            "duration_us": duration_us,
        },
        "cluster": {
            "cpu_nodes": 420,
            "physical_cores": 53760,
            "racks": 13,
        },
        "power_model": {
            "model_id": model["model_id"],
            "target": model.get("target"),
            "physical_calibrated":
                model.get("physical_calibrated", False),
        },
        "nodes": sorted(
            initialized.values(),
            key=lambda node: node["index"],
        ),
        "events": events,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(trace, indent=2) + "\n"
    )

    print("SST TRACE EXPORT")
    print(f"initialized nodes : {len(initialized)}")
    print(f"RUNNING events    : {len(running_events)}")
    print(f"END events        : {len(completion_events)}")
    print(f"total events      : {len(events)}")
    print(f"duration          : {duration_us:g} us")
    print(f"power model       : {model['model_id']}")
    print(f"output            : {output_path}")
    print("")
    print("SST TRACE EXPORT: PASS")


if __name__ == "__main__":
    main()
