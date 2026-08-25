#!/usr/bin/env bash
# ==============================================================================
# CoChem-BENCH: In-Memory tmpfs Mount & Ephemeral MPI Scratch Setup Script
# ==============================================================================
set -euo pipefail

echo "========================================================"
echo "CoChem-BENCH: Initializing Ephemeral Workspace & tmpfs"
echo "========================================================"

# Resolve the target artifacts directory dynamically from environment or default
ARTIFACTS_ROOT="${COCHEM_ARTIFACTS_DIR:-${HOME}/CoChem_Artifacts}"
SCRATCH_DIR="${ARTIFACTS_ROOT}/BENCH_Workspace/Scratch"
REGISTRY_DIR="${ARTIFACTS_ROOT}/Registry"
LOGS_DIR="${ARTIFACTS_ROOT}/BENCH_Workspace/Logs"
INPUT_DIR="${ARTIFACTS_ROOT}/BENCH_Workspace/Input_Files"
PROCESSED_DIR="${ARTIFACTS_ROOT}/BENCH_Workspace/Processed"

echo "[INFO] Artifacts Root: ${ARTIFACTS_ROOT}"
echo "[INFO] Ephemeral Scratch Directory: ${SCRATCH_DIR}"

# Create required directory hierarchy for the Bipartite Workspace Air-Gap
mkdir -p "${SCRATCH_DIR}"
mkdir -p "${REGISTRY_DIR}"
mkdir -p "${LOGS_DIR}"
mkdir -p "${INPUT_DIR}"
mkdir -p "${PROCESSED_DIR}"

# Attempt to mount tmpfs if running in a container with CAP_SYS_ADMIN privileges
if command -v mount >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    echo "[INFO] Root privileges detected; attempting in-memory tmpfs mount on ${SCRATCH_DIR}..."
    if mount -t tmpfs -o size=4G,mode=1777 tmpfs "${SCRATCH_DIR}" 2>/dev/null; then
        echo "[SUCCESS] Mounted 4GB in-memory tmpfs on ${SCRATCH_DIR}"
    else
        echo "[WARN] In-memory tmpfs mount failed (unprivileged container); utilizing local filesystem scratch."
    fi
else
    echo "[INFO] Standard container permissions; utilizing local NVMe/SSD scratch allocation."
fi

# Ensure correct permissions for scratch directory
chmod 777 "${SCRATCH_DIR}" || chmod 755 "${SCRATCH_DIR}" || true

# Export OpenMPI and temporal scratch variables for runtime processes
export TMPDIR="${SCRATCH_DIR}"
export OMPI_MCA_btl_vader_single_copy_mechanism=none
export OMPI_MCA_rmaps_base_oversubscribe=1

echo "[SUCCESS] CoChem-BENCH environment initialized."
