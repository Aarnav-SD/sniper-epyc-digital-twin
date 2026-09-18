#!/usr/bin/env bash

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_DIR="$ROOT/tools/epyc/cluster"
POWER_DIR="$ROOT/tools/epyc/power"
SST_DIR="$ROOT/tools/epyc/sst/epycnode"
POWER_MODEL="$ROOT/configs/power/cpu_power_model_v1.json"

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

section "[1/8] HARDWARE AND CLUSTER MANIFESTS"

run_test \
    "Cluster manifest consistency" \
    python3 "$CLUSTER_DIR/validate_cluster_manifest.py"

# ----------------------------------------------------------------------
# 2. Object model
# ----------------------------------------------------------------------

section "[2/8] 420-NODE CPU COMPUTE-SUBSYSTEM MODEL"

run_test \
    "CPU compute-subsystem object model" \
    python3 "$CLUSTER_DIR/validate_cluster_model.py"

# ----------------------------------------------------------------------
# 3. Runtime model
# ----------------------------------------------------------------------

section "[3/8] MULTI-NODE RUNTIME MODEL"

run_test \
    "Independent multi-node workload allocation" \
    python3 "$CLUSTER_DIR/validate_cluster_runtime.py"

# ----------------------------------------------------------------------
# 4. Calibration-safe power interface
# ----------------------------------------------------------------------

section "[4/8] REDUCED-ORDER POWER INTERFACE"

run_test \
    "Calibration-safe power-model interface" \
    python3 "$CLUSTER_DIR/validate_power_interface.py"

# ----------------------------------------------------------------------
# 5. Frozen Sniper -> McPAT surrogate artifact
# ----------------------------------------------------------------------

section "[5/8] SNIPER-MCPAT CPU POWER SURROGATE"

if [[ -f "$POWER_MODEL" ]]; then
    pass "Frozen CPU power-model artifact available"
else
    fail "Frozen CPU power-model artifact available"
fi

run_test \
    "Reduced-order CPU surrogate evaluation" \
    python3 "$POWER_DIR/evaluate_model.py" \
        "$POWER_MODEL" \
        --instruction-rate-gips 25.187

# ----------------------------------------------------------------------
# 6. SST environment/component
# ----------------------------------------------------------------------

section "[6/8] SST ENVIRONMENT"

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
# 7. Full 420-node workload-sensitive SST execution
# ----------------------------------------------------------------------

section "[7/8] FULL 420-NODE WORKLOAD-SENSITIVE SST EXECUTION"

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

    SURROGATE_REPORTS="$(
        grep -c 'power_model=mcpat-surrogate-v1' "$SST_LOG" || true
    )"

    UNSAFE_CALIBRATED="$(
        grep -c 'calibrated=true' "$SST_LOG" || true
    )"

    JOB_A_POWER="$(
        grep -c \
            'job=JOB_A.*' "$SST_LOG" || true
    )"

    JOB_B_POWER="$(
        grep -c \
            'job=JOB_B.*' "$SST_LOG" || true
    )"

    JOB_A_SURROGATE="$(
        grep -c \
            'power_model=mcpat-surrogate-v1 power_w=101.068 status=REFERENCE_ONLY calibrated=false' \
            "$SST_LOG" || true
    )"

    JOB_B_SURROGATE="$(
        grep -c \
            'power_model=mcpat-surrogate-v1 power_w=95.1022 status=REFERENCE_ONLY calibrated=false' \
            "$SST_LOG" || true
    )"

    echo "Initialized CPU nodes:        $INITIALIZED"
    echo "RUNNING transitions:          $RUNNING"
    echo "Job completions:              $COMPLETED"
    echo "Surrogate-power reports:      $SURROGATE_REPORTS"
    echo "Unsafe calibrated claims:     $UNSAFE_CALIBRATED"
    echo "JOB_A runtime records:        $JOB_A_POWER"
    echo "JOB_B runtime records:        $JOB_B_POWER"
    echo "JOB_A 101.068 W reports:      $JOB_A_SURROGATE"
    echo "JOB_B 95.1022 W reports:      $JOB_B_SURROGATE"

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

    if [[ "$SURROGATE_REPORTS" -eq 80 && \
          "$UNSAFE_CALIBRATED" -eq 0 ]]; then
        pass "Surrogate power propagated into SST"
    else
        fail "Surrogate power propagated into SST"
    fi

    if [[ "$JOB_A_SURROGATE" -eq 64 && \
          "$JOB_B_SURROGATE" -eq 16 ]]; then
        pass "Workload-sensitive per-node power differentiated"
    else
        fail "Workload-sensitive per-node power differentiated"
    fi

else
    echo "SST execution failed."
    echo
    tail -n 30 "$SST_LOG" 2>/dev/null || true
    fail "Full 420-node SST execution"
fi

# ----------------------------------------------------------------------
# 8. Time-resolved power aggregation
# ----------------------------------------------------------------------

section "[8/8] TIME-RESOLVED CLUSTER CPU POWER PIPELINE"

run_test \
    "Workload-sensitive reference-only cluster power timeline" \
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
echo "  Sniper-McPAT characterization IMPLEMENTED"
echo "  Reduced-order CPU surrogate  IMPLEMENTED"
echo "  Workload-sensitive SST power IMPLEMENTED"
echo "  Cluster CPU power timeline   IMPLEMENTED"
echo "  Physical EPYC calibration    PENDING"
echo "  GPU subsystem                FUTURE"
echo "  InfiniBand network           FUTURE"
echo "  Lustre storage               FUTURE"
echo "  PBS Pro scheduler            FUTURE"

echo
echo "Current validation scenario:"
echo "  JOB_A: 64 nodes, 25.187 GIPS/profile"
echo "         101.0680 W/node CPU-side reference estimate"
echo "  JOB_B: 16 nodes, 12.732 GIPS/profile"
echo "          95.1022 W/node CPU-side reference estimate"
echo "  Peak active CPU-side reference power: 7989.98 W"
echo "  Active-interval CPU-side reference energy: 0.829431 J"

echo
echo "Power-model interpretation:"
echo "  Workload activity originates from Sniper characterization."
echo "  CPU-side reference targets originate from McPAT."
echo "  SST uses the frozen reduced-order surrogate rather than"
echo "  executing a full Sniper/McPAT instance for every node."
echo "  Surrogate wattage and energy are REFERENCE_ONLY."
echo "  physical_calibrated=false."
echo "  McPAT uses the 22 nm compatibility configuration;"
echo "  these values are not absolute 7 nm EPYC power predictions."
echo "  Legacy Sniper DRAM power is excluded from this CPU model."
echo "  Idle-node/platform power is unavailable and is not included"
echo "  in the numerical cluster aggregate."

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
