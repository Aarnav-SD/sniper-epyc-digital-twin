#!/usr/bin/env python3

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from model import ComputeNode, NodeState


@dataclass(frozen=True)
class PowerEstimate:
    """
    Result returned by a node power model.

    calibrated=False means the value must not be interpreted as a
    physically calibrated EPYC 7763 power prediction.
    """

    power_w: Optional[float]
    model_name: str
    calibrated: bool
    status: str
    note: str = ""


class NodePowerModel(ABC):
    """Interface implemented by all cluster-level node power models."""

    @abstractmethod
    def estimate(self, node: ComputeNode) -> PowerEstimate:
        raise NotImplementedError


class PendingCalibrationPowerModel(NodePowerModel):
    """
    Safe placeholder used before physical EPYC calibration.

    Deliberately returns no wattage rather than fabricating a relationship
    between core utilization and the single available McPAT experiment.
    """

    def estimate(self, node: ComputeNode) -> PowerEstimate:

        if node.runtime.state == NodeState.DOWN:
            return PowerEstimate(
                power_w=None,
                model_name="pending-calibration",
                calibrated=False,
                status="UNAVAILABLE",
                note="Node is down; calibrated platform power unavailable."
            )

        return PowerEstimate(
            power_w=None,
            model_name="pending-calibration",
            calibrated=False,
            status="PENDING",
            note=(
                "Physical EPYC 7763 power calibration has not yet "
                "been performed."
            )
        )


class FixedMcPATReferenceModel(NodePowerModel):
    """
    Diagnostic/reference backend.

    This exposes the raw CPU-side McPAT value from one validated experiment
    for pipeline testing ONLY.

    It is NOT a workload-dependent cluster power model and MUST NOT be used
    as a calibrated EPYC 7763 prediction.
    """

    def __init__(self, reference_power_w: float = 88.48):
        self.reference_power_w = reference_power_w

    def estimate(self, node: ComputeNode) -> PowerEstimate:

        if node.runtime.state != NodeState.RUNNING:
            return PowerEstimate(
                power_w=None,
                model_name="mcpat-reference",
                calibrated=False,
                status="UNAVAILABLE",
                note=(
                    "Reference McPAT point is defined only for the "
                    "validated active workload."
                )
            )

        return PowerEstimate(
            power_w=self.reference_power_w,
            model_name="mcpat-reference",
            calibrated=False,
            status="REFERENCE_ONLY",
            note=(
                "Raw CPU-side McPAT reference point. "
                "Not calibrated to physical EPYC 7763 hardware and "
                "not scaled by utilization."
            )
        )
