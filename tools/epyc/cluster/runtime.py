#!/usr/bin/env python3

from dataclasses import dataclass
from typing import List

from model import ComputeNode, NodeState


@dataclass(frozen=True)
class Job:
    job_id: str
    num_nodes: int
    cores_per_node: int
    utilization: float = 1.0


class CpuCluster:
    def __init__(self, nodes: List[ComputeNode]):
        self.nodes = nodes

    @property
    def total_nodes(self):
        return len(self.nodes)

    @property
    def idle_nodes(self):
        return [
            node for node in self.nodes
            if node.runtime.state == NodeState.IDLE
        ]

    @property
    def running_nodes(self):
        return [
            node for node in self.nodes
            if node.runtime.state == NodeState.RUNNING
        ]

    @property
    def active_cores(self):
        return sum(
            node.runtime.active_cores
            for node in self.nodes
        )

    def allocate(self, job: Job):
        if job.num_nodes <= 0:
            raise ValueError("num_nodes must be positive")

        if job.cores_per_node <= 0:
            raise ValueError("cores_per_node must be positive")

        if not 0.0 <= job.utilization <= 1.0:
            raise ValueError("utilization must be between 0 and 1")

        if any(
            node.runtime.job_id == job.job_id
            for node in self.nodes
        ):
            raise ValueError(
                f"job {job.job_id!r} is already allocated"
            )

        available = self.idle_nodes

        if len(available) < job.num_nodes:
            raise RuntimeError(
                f"job {job.job_id!r} requests {job.num_nodes} nodes, "
                f"but only {len(available)} are idle"
            )

        selected = available[:job.num_nodes]

        # Validate before modifying any node so allocation is atomic.
        for node in selected:
            if job.cores_per_node > node.hardware.total_cores:
                raise ValueError(
                    f"job requests {job.cores_per_node} cores/node, "
                    f"but {node.node_id} has only "
                    f"{node.hardware.total_cores}"
                )

        for node in selected:
            node.assign_job(
                job_id=job.job_id,
                active_cores=job.cores_per_node,
                utilization=job.utilization,
            )

        return selected

    def release(self, job_id: str):
        allocated = [
            node for node in self.nodes
            if node.runtime.job_id == job_id
        ]

        for node in allocated:
            node.release_job()

        return len(allocated)

    def nodes_for_job(self, job_id: str):
        return [
            node for node in self.nodes
            if node.runtime.job_id == job_id
        ]

    def estimate_power(self, power_model):
        """
        Evaluate the selected power backend independently for every node.

        Returns both per-node estimates and a cluster aggregate.
        The aggregate is only considered available when every running node
        has a numerical estimate.
        """

        estimates = {}

        running_power = 0.0
        running_with_power = 0

        for node in self.nodes:
            estimate = power_model.estimate(node)
            estimates[node.node_id] = estimate

            if (
                node.runtime.state == NodeState.RUNNING
                and estimate.power_w is not None
            ):
                running_power += estimate.power_w
                running_with_power += 1

        running_nodes = len(self.running_nodes)

        complete = (
            running_nodes > 0
            and running_with_power == running_nodes
        )

        return {
            "per_node": estimates,
            "running_nodes": running_nodes,
            "nodes_with_power": running_with_power,
            "aggregate_power_w": (
                running_power if complete else None
            ),
            "complete": complete,
            "calibrated": (
                complete
                and all(
                    estimates[node.node_id].calibrated
                    for node in self.running_nodes
                )
            ),
        }