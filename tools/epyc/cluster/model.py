#!/usr/bin/env python3

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DOWN = "down"


@dataclass(frozen=True)
class NodeHardware:
    """Immutable hardware description shared by identical compute nodes."""

    type_id: str
    server_model: str
    cpu_model: str

    sockets: int
    cores_per_socket: int
    total_cores: int

    numa_nodes: int
    cores_per_numa: int

    l3_groups: int
    dram_controllers: int

    memory_gib: int


@dataclass
class NodeRuntimeState:
    """Runtime state unique to each physical compute node."""

    state: NodeState = NodeState.IDLE

    active_cores: int = 0
    utilization: float = 0.0

    memory_bandwidth_gbps: float = 0.0

    raw_cpu_power_w: Optional[float] = None
    calibrated_cpu_power_w: Optional[float] = None

    job_id: Optional[str] = None


@dataclass
class ComputeNode:
    """One independently addressable CPU compute node."""

    node_id: str
    global_index: int

    rack_id: str
    rack_type: str
    rack_local_index: int

    hardware: NodeHardware

    runtime: NodeRuntimeState = field(
        default_factory=NodeRuntimeState
    )

    def assign_job(
        self,
        job_id: str,
        active_cores: int,
        utilization: float = 1.0,
    ):
        if not 1 <= active_cores <= self.hardware.total_cores:
            raise ValueError(
                f"{self.node_id}: active_cores must be between "
                f"1 and {self.hardware.total_cores}"
            )

        if not 0.0 <= utilization <= 1.0:
            raise ValueError(
                f"{self.node_id}: utilization must be between 0 and 1"
            )

        self.runtime.state = NodeState.RUNNING
        self.runtime.job_id = job_id
        self.runtime.active_cores = active_cores
        self.runtime.utilization = utilization

    def release_job(self):
        self.runtime = NodeRuntimeState()

    @property
    def is_idle(self):
        return self.runtime.state == NodeState.IDLE
