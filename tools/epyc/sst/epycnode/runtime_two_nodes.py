import os
import json
import sst


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNIPER_ROOT = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../..")
)

HARDWARE_PATH = os.path.join(
    SNIPER_ROOT,
    "configs/hardware/r6525_epyc7763.json"
)

CLUSTER_PATH = os.path.join(
    SNIPER_ROOT,
    "configs/cluster/internship_hpc.json"
)


with open(HARDWARE_PATH, "r") as f:
    hardware = json.load(f)

with open(CLUSTER_PATH, "r") as f:
    cluster = json.load(f)


if cluster["cpu_compute"]["node_type"] != hardware["id"]:
    raise RuntimeError(
        "Cluster CPU node type does not match hardware manifest"
    )


def hardware_params():
    return {
        "server_model": hardware["platform"]["model"],
        "cpu_model": hardware["cpu"]["model"],
        "sockets": hardware["cpu"]["sockets"],
        "cores_per_socket": hardware["cpu"]["cores_per_socket"],
        "total_cores": hardware["cpu"]["total_physical_cores"],
        "numa_nodes": hardware["numa"]["total_nodes"],
        "cores_per_numa": hardware["numa"]["cores_per_node"],
        "l3_groups": hardware["cache"]["l3_groups"],
        "cores_per_l3": hardware["cache"]["l3_shared_cores"],
        "dram_controllers": hardware["memory"]["controllers"],
        "memory_gib": hardware["memory"]["capacity_gib"],
    }


def create_job_node(node_index):
    params = hardware_params()

    params.update({
        "node_id": f"CPU{node_index:03d}",
        "rack_id": "R00",
        "rack_type": "regular",

        # Synthetic JOB_A runtime specification
        "job_id": "JOB_A",
        "job_start_us": 10,
        "job_duration_us": 100,
        "active_cores": 128,
        "utilization": 1.0,
    })

    node = sst.Component(
        f"CPU{node_index:03d}",
        "epyctwin.EpycNode"
    )

    node.addParams(params)

    return node


print("=" * 60)
print(" SST RUNTIME TEST - TWO CPU NODES")
print("=" * 60)
print("Job                  : JOB_A")
print("Allocated CPU nodes  : CPU000, CPU001")
print("Start time            : 10 us")
print("Duration              : 100 us")
print("Expected completion   : 110 us")
print("Active cores/node     : 128")
print("Utilization           : 1.0")
print("=" * 60)


create_job_node(0)
create_job_node(1)
