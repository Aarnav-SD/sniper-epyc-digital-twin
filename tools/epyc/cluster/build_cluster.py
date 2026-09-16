#!/usr/bin/env python3

import json
from pathlib import Path

from model import ComputeNode, NodeHardware


ROOT = Path(__file__).resolve().parents[3]

NODE_MANIFEST = ROOT / "configs/hardware/r6525_epyc7763.json"
CLUSTER_MANIFEST = ROOT / "configs/cluster/internship_hpc.json"


def load_json(path):
    with path.open() as f:
        return json.load(f)


def build_hardware(node):
    return NodeHardware(
        type_id=node["id"],

        server_model=(
            f"{node['platform']['vendor']} "
            f"{node['platform']['model']}"
        ),

        cpu_model=node["cpu"]["model"],

        sockets=node["cpu"]["sockets"],
        cores_per_socket=node["cpu"]["cores_per_socket"],
        total_cores=node["cpu"]["total_physical_cores"],

        numa_nodes=node["numa"]["total_nodes"],
        cores_per_numa=node["numa"]["cores_per_node"],

        l3_groups=node["cache"]["l3_groups"],
        dram_controllers=node["memory"]["controllers"],

        memory_gib=node["memory"]["capacity_gib"],
    )


def build_cluster():
    node_manifest = load_json(NODE_MANIFEST)
    cluster_manifest = load_json(CLUSTER_MANIFEST)

    hardware = build_hardware(node_manifest)

    nodes = []
    global_index = 0

    regular = cluster_manifest["racks"]["regular"]
    special = cluster_manifest["racks"]["special"]

    # Regular racks: 11 × 38 CPU nodes
    for rack_index in range(regular["count"]):

        rack_id = f"R{rack_index:02d}"

        for local_index in range(
            regular["cpu_nodes_per_rack"]
        ):
            nodes.append(
                ComputeNode(
                    node_id=f"CPU{global_index:03d}",
                    global_index=global_index,
                    rack_id=rack_id,
                    rack_type="regular",
                    rack_local_index=local_index,
                    hardware=hardware,
                )
            )

            global_index += 1

    # Special racks follow the regular racks.
    special_rack_offset = regular["count"]

    for special_index in range(special["count"]):

        rack_index = special_rack_offset + special_index
        rack_id = f"R{rack_index:02d}"

        for local_index in range(
            special["cpu_nodes_per_rack"]
        ):
            nodes.append(
                ComputeNode(
                    node_id=f"CPU{global_index:03d}",
                    global_index=global_index,
                    rack_id=rack_id,
                    rack_type="special",
                    rack_local_index=local_index,
                    hardware=hardware,
                )
            )

            global_index += 1

    expected = cluster_manifest["cpu_compute"]["total_nodes"]

    if len(nodes) != expected:
        raise RuntimeError(
            f"Built {len(nodes)} CPU nodes, expected {expected}"
        )

    return nodes


if __name__ == "__main__":
    nodes = build_cluster()

    print(f"CPU nodes instantiated: {len(nodes)}")
    print(f"First node: {nodes[0]}")
    print(f"Last node : {nodes[-1]}")
