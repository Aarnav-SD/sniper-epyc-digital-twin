#!/usr/bin/env bash

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_DIR="$ROOT/tools/epyc/cluster"
SST_DIR="$ROOT/tools/epyc/sst/epycnode"

PASS_COUNT=0
FAIL_COUNT=0

line() {
    printf '%*s\n' 78 '' | tr ' ' '='
}

section() {
    echo
    line
    echo "$1"
    line
}

pass() {
    echo "[PASS] $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
    echo "[FAIL] $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

run_test() {
    local label="$1"
    shift

    echo
    echo "--- $label ---"

    if "$@"; then
        pass "$label"
    else
        fail "$label"
    fi
}

cd "$ROOT" || exit 1

clear 2>/dev/null || true

line
echo "          HPC DIGITAL TWIN - CPU COMPUTE SUBSYSTEM"
line

echo
echo "Reference platform:"
echo "  Dell PowerEdge R6525"
echo "  2 x AMD EPYC 7763"
echo "  128 physical cores/node"
echo "  NPS4: 8 NUMA domains/node"
echo "  16 shared-L3 groups/node"
echo "  16 DRAM controllers/node"
echo
echo "Reference cluster:"
echo "  13 racks"
echo "  420 CPU compute nodes"
echo "  53,760 physical CPU cores"

# ----------------------------------------------------------------------
# 1. Manifest consistency
# ----------------------------------------------------------------------

section "[1/7] HARDWARE AND CLUSTER MANIFESTS"

run_test \
    "Cluster manifest consistency" \
    python3 "$CLUSTER_DIR/validate_cluster_manifest.py"

# ----------------------------------------------------------------------
# 2. Object model
# ----------------------------------------------------------------------

section "[2/7] 420-NODE CPU COMPUTE-SUBSYSTEM MODEL"

run_test \
    "CPU compute-subsystem object model" \
    python3 "$CLUSTER_DIR/validate_cluster_model.py"

# ----------------------------------------------------------------------
# 3. Runtime model
# ----------------------------------------------------------------------

section "[3/7] MULTI-NODE RUNTIME MODEL"

run_test \
    "Independent multi-node workload allocation" \
    python3 "$CLUSTER_DIR/validate_cluster_runtime.py"

# ----------------------------------------------------------------------
# 4. Power interface
# ----------------------------------------------------------------------

section "[4/7] REDUCED-ORDER POWER INTERFACE"

run_test \
    "Calibration-safe power-model interface" \
    python3 "$CLUSTER_DIR/validate_power_interface.py"

# ----------------------------------------------------------------------
# 5. SST environment/component
# ----------------------------------------------------------------------

section "[5/7] SST ENVIRONMENT"

if command -v sst >/dev/null 2>&1; then
    SST_VERSION="$(sst --version 2>/dev/null | head -n 1)"

    if [[ -n "$SST_VERSION" ]]; then
        echo "SST runtime: $SST_VERSION"
        pass "SST runtime available"
    else
        fail "SST runtime available"
    fi
else
    fail "SST runtime available"
fi

if command -v sst-info >/dev/null 2>&1 && \
   sst-info epyctwin >/dev/null 2>&1; then
    pass "Custom epyctwin SST element registered"
else
    fail "Custom epyctwin SST element registered"
fi

# ----------------------------------------------------------------------
# 6. Full 420-node SST runtime
# ----------------------------------------------------------------------

section "[6/7] FULL 420-NODE SST MULTI-JOB EXECUTION"

SST_LOG="$(mktemp)"
trap 'rm -f "$SST_LOG"' EXIT

if command -v sst >/dev/null 2>&1 && \
   (cd "$SST_DIR" && sst runtime_cluster.py >"$SST_LOG" 2>&1); then

    INITIALIZED="$(
        grep -cE '^\[CPU[0-9]{3}\] initialized$' "$SST_LOG" || true
    )"

    RUNNING="$(
        grep -c 'state=RUNNING' "$SST_LOG" || true
    )"

    COMPLETED="$(
        grep -c 'state=IDLE job=.* completed' "$SST_LOG" || true
    )"

    POWER_REPORTS="$(
        grep -c 'status=REFERENCE_ONLY' "$SST_LOG" || true
    )"

    UNSAFE_CALIBRATED="$(
        grep -c 'calibrated=true' "$SST_LOG" || true
    )"

    echo "Initialized CPU nodes:        $INITIALIZED"
    echo "RUNNING transitions:          $RUNNING"
    echo "Job completions:              $COMPLETED"
    echo "Reference-power reports:      $POWER_REPORTS"
    echo "Unsafe calibrated claims:     $UNSAFE_CALIBRATED"

    if [[ "$INITIALIZED" -eq 420 ]]; then
        pass "420 SST CPU nodes instantiated"
    else
        fail "420 SST CPU nodes instantiated"
    fi

    if [[ "$RUNNING" -eq 80 && "$COMPLETED" -eq 80 ]]; then
        pass "Manifest-driven concurrent jobs executed"
    else
        fail "Manifest-driven concurrent jobs executed"
    fi

    if [[ "$POWER_REPORTS" -eq 80 && "$UNSAFE_CALIBRATED" -eq 0 ]]; then
        pass "Runtime-to-power propagation"
    else
        fail "Runtime-to-power propagation"
    fi

else
    echo "SST execution failed."
    echo
    tail -n 30 "$SST_LOG" 2>/dev/null || true
    fail "Full 420-node SST execution"
fi

# ----------------------------------------------------------------------
# 7. Time-resolved power aggregation
# ----------------------------------------------------------------------

section "[7/7] TIME-RESOLVED CLUSTER POWER PIPELINE"

run_test \
    "Reference-only cluster power timeline" \
    python3 "$SST_DIR/validate_power_timeline.py"

# ----------------------------------------------------------------------
# Final status
# ----------------------------------------------------------------------

section "DIGITAL TWIN VALIDATION SUMMARY"

echo "Executable checks passed: $PASS_COUNT"
echo "Executable checks failed: $FAIL_COUNT"

echo
echo "Current scope status:"
echo "  CPU compute subsystem        IMPLEMENTED"
echo "  420-node SST representation  IMPLEMENTED"
echo "  Multi-job runtime            IMPLEMENTED"
echo "  Runtime-to-power pipeline    IMPLEMENTED"
echo "  Physical EPYC calibration    PENDING"
echo "  GPU subsystem                FUTURE"
echo "  InfiniBand network           FUTURE"
echo "  Lustre storage               FUTURE"
echo "  PBS Pro scheduler            FUTURE"

echo
echo "Power-model interpretation:"
echo "  McPAT wattage is REFERENCE_ONLY and calibrated=false."
echo "  It must not be interpreted as physical EPYC 7763 power."
echo "  Idle platform power is not yet numerically modeled."

echo
line

if [[ "$FAIL_COUNT" -eq 0 ]]; then
    echo "CPU DIGITAL TWIN VALIDATION: PASS"
    line
    exit 0
else
    echo "CPU DIGITAL TWIN VALIDATION: FAIL ($FAIL_COUNT check(s))"
    line
    exit 1
fi
