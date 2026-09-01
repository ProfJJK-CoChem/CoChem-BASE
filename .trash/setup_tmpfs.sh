#!/usr/bin/env bash
# ==============================================================================
# CoChem-BENCH: Transient In-Memory RAM-Disk (tmpfs) Setup Script
# ==============================================================================
# Purpose: Sets up a high-speed transient RAM-disk (tmpfs) for ephemeral quantum
# chemistry computations, wavefunctions (.gbw), and heavy intermediate tensors.
#
# Constraints & Safety Contracts:
# 1. Strictly bound to the $COCHEM_ARTIFACTS_DIR environment variable.
# 2. Evaluates MOUNT_POINT via: eval MOUNT_POINT="$COCHEM_ARTIFACTS_DIR/Scratch_RAM"
# 3. Fails immediately with exit code 1 if $COCHEM_ARTIFACTS_DIR is not set.
# 4. Zero hardcoded absolute paths (Air-Gap compliance).
# 5. Safe tmpfs mount with automatic graceful fallback for unprivileged environments.
# ==============================================================================

set -euo pipefail

# 1. Enforce Stage 0 Artifact Directory Environment Variable
if [ -z "${COCHEM_ARTIFACTS_DIR:-}" ]; then
    echo "[ERROR] COCHEM_ARTIFACTS_DIR is not set. Ephemeral RAM-disk initialization aborted." >&2
    exit 1
fi

# 2. Dynamically bind the mount point strictly from COCHEM_ARTIFACTS_DIR
eval MOUNT_POINT="$COCHEM_ARTIFACTS_DIR/Scratch_RAM"

echo "========================================================"
echo "CoChem-BENCH: Initializing Transient RAM-Disk (tmpfs)"
echo "========================================================"
echo "[INFO] Target Mount Point: ${MOUNT_POINT}"

# 3. Ensure mount directory exists
mkdir -p "${MOUNT_POINT}"

# 4. Attempt tmpfs mount if running in a privileged container or root environment
if command -v mount >/dev/null 2>&1 && [ "$(id -u 2>/dev/null || echo 1)" -eq 0 ]; then
    echo "[INFO] Root/privileged context detected. Attempting in-memory tmpfs mount on ${MOUNT_POINT}..."
    if mount -t tmpfs -o size=4G,mode=1777 tmpfs "${MOUNT_POINT}" 2>/dev/null; then
        echo "[SUCCESS] Mounted 4GB in-memory tmpfs on ${MOUNT_POINT}"
    else
        echo "[WARN] In-memory tmpfs mount failed (insufficient permissions/capabilities); utilizing local directory fallback."
    fi
else
    echo "[INFO] Standard non-root permissions; utilizing local filesystem scratch at ${MOUNT_POINT}."
fi

# 5. Set appropriate permissions
chmod 777 "${MOUNT_POINT}" 2>/dev/null || chmod 755 "${MOUNT_POINT}" 2>/dev/null || true

# 6. Export runtime scratch variables
export TMPDIR="${MOUNT_POINT}"
export COCHEM_SCRATCH_RAM="${MOUNT_POINT}"

echo "[SUCCESS] Transient RAM-disk ready at ${MOUNT_POINT}"
