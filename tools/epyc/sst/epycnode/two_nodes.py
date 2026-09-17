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


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


hardware = load_json(HARDWARE_MANIFEST)
cluster = load_json(CLUSTER_MANIFEST)


# ------------------------------------------------------------
# Cross-manifest safety check
# ------------------------------------------------------------

if cluster["cpu_compute"]["node_type"] != hardware["id"]:
    raise RuntimeError(
        "Cluster CPU node type does not match hardware manifest: "
        f'{cluster["cpu_compute"]["node_type"]} != {hardware["id"]}'
    )


# ------------------------------------------------------------
# Translate canonical hardware manifest -> SST EpycNode params
# ------------------------------------------------------------

def hardware_params():
    cpu = hardware["cpu"]
    cache = hardware["cache"]
    numa = hardware["numa"]
    memory = hardware["memory"]
    platform = hardware["platform"]

    return {
        "server_model": (
            f'{platform["vendor"]} {platform["model"]}'
        ),
        "cpu_model": cpu["model"],

        "sockets": cpu["sockets"],
        "cores_per_socket": cpu["cores_per_socket"],
        "total_cores": cpu["total_physical_cores"],

        "numa_nodes": numa["total_nodes"],
        "cores_per_numa": numa["cores_per_node"],

        "l3_groups": cache["l3_groups"],
        "cores_per_l3": cache["l3_shared_cores"],

        "dram_controllers": memory["controllers"],
        "memory_gib": memory["capacity_gib"],
    }


# ------------------------------------------------------------
# Instantiate one SST reduced-order CPU node
# ------------------------------------------------------------

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

    component.addParams(params)

    return component


# ------------------------------------------------------------
# Two-node integration test
#
# Both nodes belong to regular rack R00.
# The cluster manifest says each regular rack contains 38 CPU
# nodes, so CPU000 and CPU001 are both valid members of R00.
# ------------------------------------------------------------

create_cpu_node(
    global_index=0,
    rack_id="R00",
    rack_type="regular"
)

create_cpu_node(
    global_index=1,
    rack_id="R00",
    rack_type="regular"
)


print("[SST CONFIG] Hardware manifest:", hardware["id"])
print("[SST CONFIG] Cluster manifest:", cluster["id"])
print("[SST CONFIG] Test CPU nodes: 2")
