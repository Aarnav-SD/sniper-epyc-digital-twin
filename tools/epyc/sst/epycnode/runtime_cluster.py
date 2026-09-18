from pathlib import Path
import json
import os
import sst


# Repository root:
# tools/epyc/sst/epycnode/<script>.py -> ../../../../ -> repo root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNIPER_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../..")
)

HARDWARE_MANIFEST = os.path.join(
    SNIPER_ROOT,
    "configs/hardware/r6525_epyc7763.json"
)

CLUSTER_MANIFEST = os.path.join(
    SNIPER_ROOT,
    "configs/cluster/internship_hpc.json"
)

WORKLOAD_MANIFEST = os.path.join(
    SNIPER_ROOT,
    "configs/workloads/sst_multijob_validation.json"
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


hardware = load_json(HARDWARE_MANIFEST)
cluster = load_json(CLUSTER_MANIFEST)
workload = load_json(WORKLOAD_MANIFEST)

if workload["schema_version"] != 1:
    raise RuntimeError(
        f'Unsupported workload schema version: '
        f'{workload["schema_version"]}'
    )

jobs = workload["jobs"]

if not jobs:
    raise RuntimeError(
        "Workload scenario must contain at least one job"
    )

total_requested_nodes = sum(
    job["num_nodes"] for job in jobs
)

if total_requested_nodes > cluster["cpu_compute"]["total_nodes"]:
    raise RuntimeError(
        "Workload requests more CPU nodes than the cluster contains"
    )


# ------------------------------------------------------------
# Cross-manifest validation
# ------------------------------------------------------------

if cluster["cpu_compute"]["node_type"] != hardware["id"]:
    raise RuntimeError(
        "Cluster CPU node type does not match hardware manifest: "
        f'{cluster["cpu_compute"]["node_type"]} != {hardware["id"]}'
    )


# ------------------------------------------------------------
# Reduced-order CPU power surrogate
# ------------------------------------------------------------

def evaluate_cpu_power_surrogate(power_config, job):
    if power_config["model"] != "mcpat-surrogate-v1":
        raise RuntimeError(
            "Unsupported surrogate power model: "
            f'{power_config["model"]}'
        )

    model_path = Path(SNIPER_ROOT) / power_config["model_file"]

    with model_path.open() as f:
        model = json.load(f)

    if model["model_id"] != "epyc7763_mcpat_cpu_surrogate_v1":
        raise RuntimeError(
            "Unexpected CPU power model: "
            f'{model["model_id"]}'
        )

    if model["target"]["physical_calibrated"]:
        raise RuntimeError(
            "Reference surrogate must not claim physical calibration"
        )

    activity = job.get("activity")

    if not activity:
        raise RuntimeError(
            f'{job["job_id"]}: mcpat-surrogate-v1 requires '
            "an explicit activity profile"
        )

    if activity.get("source") != "sniper-characterization":
        raise RuntimeError(
            f'{job["job_id"]}: unsupported activity source'
        )

    rate = float(activity["instruction_rate_gips"])

    domain = model["training_domain"]
    rate_min = float(domain["instruction_rate_gips_min"])
    rate_max = float(domain["instruction_rate_gips_max"])

    if not rate_min <= rate <= rate_max:
        raise RuntimeError(
            f'{job["job_id"]}: instruction rate {rate} GIPS '
            f'outside surrogate training domain '
            f'[{rate_min}, {rate_max}] GIPS'
        )

    eq = model["equation"]

    power_w = (
        float(eq["intercept_w"])
        + float(eq["instruction_rate_gips_coefficient"])
        * rate
    )

    return power_w


# ------------------------------------------------------------
# Canonical hardware manifest -> SST EpycNode parameters
# ------------------------------------------------------------

def hardware_params():
    platform = hardware["platform"]
    cpu = hardware["cpu"]
    cache = hardware["cache"]
    numa = hardware["numa"]
    memory = hardware["memory"]

    return {
        "server_model":
            f'{platform["vendor"]} {platform["model"]}',

        "cpu_model":
            cpu["model"],

        "sockets":
            cpu["sockets"],

        "cores_per_socket":
            cpu["cores_per_socket"],

        "total_cores":
            cpu["total_physical_cores"],

        "numa_nodes":
            numa["total_nodes"],

        "cores_per_numa":
            numa["cores_per_node"],

        "l3_groups":
            cache["l3_groups"],

        "cores_per_l3":
            cache["l3_shared_cores"],

        "dram_controllers":
            memory["controllers"],

        "memory_gib":
            memory["capacity_gib"],
    }


def create_cpu_node(global_index, rack_id, rack_type):
    node_id = f"CPU{global_index:03d}"

    params = hardware_params()

    params.update({
        "node_id": node_id,
        "rack_id": rack_id,
        "rack_type": rack_type,
    })

    component = sst.Component(
        node_id,
        "epyctwin.EpycNode"
    )

    # Deterministic contiguous first-fit placement.
    # This is workload placement for runtime validation, not PBS Pro.
    allocation_start = 0

    for job in jobs:
        allocation_end = allocation_start + job["num_nodes"]

        if allocation_start <= global_index < allocation_end:
            params.update({
                "job_id": job["job_id"],
                "job_start_us": job["start_us"],
                "job_duration_us": job["duration_us"],
                "active_cores": job["cores_per_node"],
                "utilization": job["utilization"],
            })

            # Optional scenario-level power backend.
            power = workload.get("power", {})

            if power:
                power_model = power["model"]

                if power_model == "mcpat-surrogate-v1":
                    reference_power_w = (
                        evaluate_cpu_power_surrogate(
                            power,
                            job,
                        )
                    )

                elif power_model == "mcpat-reference":
                    reference_power_w = power.get(
                        "reference_power_w",
                        88.48,
                    )

                elif power_model == "pending-calibration":
                    reference_power_w = 0.0

                else:
                    raise RuntimeError(
                        "Unsupported power model: "
                        f"{power_model}"
                    )

                params.update({
                    "power_model": power_model,
                    "reference_power_w":
                        reference_power_w,
                })
            break

        allocation_start = allocation_end

    component.addParams(params)

    return component


# ------------------------------------------------------------
# Build rack topology directly from cluster manifest
# ------------------------------------------------------------

regular = cluster["racks"]["regular"]
special = cluster["racks"]["special"]

nodes = []
global_index = 0


# Regular racks R00-R10
for rack_index in range(regular["count"]):
    rack_id = f"R{rack_index:02d}"

    for _ in range(regular["cpu_nodes_per_rack"]):
        nodes.append(
            create_cpu_node(
                global_index=global_index,
                rack_id=rack_id,
                rack_type="regular"
            )
        )

        global_index += 1


# Special racks R11-R12
special_rack_start = regular["count"]

for local_rack_index in range(special["count"]):
    rack_index = special_rack_start + local_rack_index
    rack_id = f"R{rack_index:02d}"

    for _ in range(special["cpu_nodes_per_rack"]):
        nodes.append(
            create_cpu_node(
                global_index=global_index,
                rack_id=rack_id,
                rack_type="special"
            )
        )

        global_index += 1


# ------------------------------------------------------------
# Structural validation before simulation begins
# ------------------------------------------------------------

expected_nodes = cluster["cpu_compute"]["total_nodes"]
actual_nodes = len(nodes)

if actual_nodes != expected_nodes:
    raise RuntimeError(
        f"CPU node-count mismatch: "
        f"constructed={actual_nodes}, declared={expected_nodes}"
    )


regular_nodes = (
    regular["count"] *
    regular["cpu_nodes_per_rack"]
)

special_nodes = (
    special["count"] *
    special["cpu_nodes_per_rack"]
)

if regular_nodes + special_nodes != expected_nodes:
    raise RuntimeError(
        "Rack population does not reproduce declared CPU-node count"
    )


cores_per_node = hardware["cpu"]["total_physical_cores"]
numa_per_node = hardware["numa"]["total_nodes"]
l3_per_node = hardware["cache"]["l3_groups"]
dram_controllers_per_node = hardware["memory"]["controllers"]
memory_per_node_gib = hardware["memory"]["capacity_gib"]

total_cores = actual_nodes * cores_per_node
total_numa = actual_nodes * numa_per_node
total_l3 = actual_nodes * l3_per_node
total_dram_controllers = actual_nodes * dram_controllers_per_node
total_memory_gib = actual_nodes * memory_per_node_gib


# ------------------------------------------------------------
# Configuration summary
# ------------------------------------------------------------

print()
print("============================================================")
print(" INTERNSHIP HPC - SST CPU COMPUTE SUBSYSTEM")
print("============================================================")
print(f"Hardware model       : {hardware['id']}")
print(f"Cluster model        : {cluster['id']}")
print(f"Regular racks        : {regular['count']}")
print(f"Special racks        : {special['count']}")
print(f"Total racks          : {regular['count'] + special['count']}")
print(f"Regular CPU nodes    : {regular_nodes}")
print(f"Special CPU nodes    : {special_nodes}")
print(f"Total CPU nodes      : {actual_nodes}")
print(f"Physical CPU cores   : {total_cores}")
print(f"NUMA domains         : {total_numa}")
print(f"L3 groups            : {total_l3}")
print(f"DRAM controllers     : {total_dram_controllers}")
print(f"Node-local memory    : {total_memory_gib} GiB")
print("============================================================")
print("CPU cluster construction: PASS")
print("============================================================")
print()
