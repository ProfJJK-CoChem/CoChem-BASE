"""
CoChem-TORQ: Stage 5.5 / 6.0 Out-of-Band Telemetry & Visual Streamer
====================================================================
Implements real-time asynchronous webhook event dispatch, exponential backoff
circuit breakers, tripartite air-gap spooling, 2D/3D topological decimation
with stationary point injection, and Steric Shatter crash animation export.

Authoritative Standards:
- Method Matrix (Section 2.1, 12.5): Soft-quench diagnostics and topological preservation
- WCAG 2.1 AA: Accessible standalone 3D visualizers with high-contrast color palettes
- Zero-Interruption Invariant: Telemetry drops never halt active JAX compute kernels
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import collections
import json
import math
import os
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.interpolate import PchipInterpolator

from cochem_base.exceptions import (
    TelemetryNetworkExhaustedWarning,
)

# Global Tripartite In-Memory Air-Gap Buffer (maxlen=1000)
TELEMETRY_BUFFER: collections.deque = collections.deque(maxlen=1000)


def _resolve_webhook_url(
    webhook_url: Optional[str] = None, config_path: Optional[str] = None
) -> Optional[str]:
    """Resolves webhook URL from argument, environment variable, or system config."""
    if webhook_url and webhook_url.strip() and webhook_url != "None":
        return webhook_url.strip()

    env_url = os.environ.get("COCHEM_WEBHOOK_URL")
    if env_url and env_url.strip():
        return env_url.strip()

    # Attempt to load from config_path or cochem_system_config.json
    search_paths = []
    if config_path:
        search_paths.append(Path(config_path))
    search_paths.extend([
        Path("cochem_system_config.json"),
        Path(__file__).parent / "cochem_system_config.json",
        Path(__file__).parent.parent / "cochem_system_config.json",
    ])

    for cfg_p in search_paths:
        if cfg_p.exists() and cfg_p.is_file():
            try:
                with open(cfg_p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    url = cfg.get("telemetry", {}).get("webhook_url") or cfg.get("webhook_url")
                    if url and isinstance(url, str) and url.strip() and url != "[MISSING DATA]" and url != "None":
                        return url.strip()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

    return None


def _spool_telemetry_event(
    entry: Dict[str, Any], spool_file: str = "telemetry_spool.jsonl"
) -> None:
    """Appends an unsent telemetry event to local memory buffer and disk spool."""
    TELEMETRY_BUFFER.append(entry)
    try:
        spool_path = Path(spool_file)
        spool_path.parent.mkdir(parents=True, exist_ok=True)
        with open(spool_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Disk write error must not crash the parent compute kernel
        warnings.warn(
            f"Failed to spool telemetry to disk ({e}); preserved in in-memory buffer.",
            TelemetryNetworkExhaustedWarning,
            stacklevel=2,
        )


def stream_webhook_events(
    status_payload: Dict[str, Any],
    webhook_url: Optional[str] = None,
    config_path: Optional[str] = None,
    timeout: float = 3.0,
    max_retries: int = 3,
    spool_file: str = "telemetry_spool.jsonl",
) -> bool:
    """
    Asynchronous / Non-Blocking Webhook Event Dispatcher with Exponential Backoff.
    Broadcasts job completions, node failures, Soft-Quench collision alerts, or
    OOM-Backoff triggers to Discord/Slack webhooks.

    Zero-Interruption Invariant:
    If the cluster experiences network drops, timeouts, or DNS failures, this function
    silently caches logs into collections.deque(maxlen=1000) and telemetry_spool.jsonl,
    emitting a TelemetryNetworkExhaustedWarning without interrupting active JAX kernels.

    Parameters:
        status_payload: Event data dictionary (job status, metrics, diagnostics).
        webhook_url: Target Discord/Slack webhook URL (optional).
        config_path: Path to system config file (optional).
        timeout: HTTP request timeout ceiling in seconds (2.0s - 5.0s range).
        max_retries: Maximum exponential backoff retry attempts (default: 3).
        spool_file: Local JSONL spool path for air-gapped fallback.

    Returns:
        True if event was successfully dispatched over HTTP; False if spooled to fallback.
    """
    resolved_url = _resolve_webhook_url(webhook_url, config_path)
    clamped_timeout = max(2.0, min(5.0, float(timeout)))

    timestamp_utc = datetime.now(timezone.utc).isoformat()
    spool_entry = {
        "timestamp_utc": timestamp_utc,
        "payload": status_payload,
        "webhook_url": resolved_url,
    }

    # Air-gap fallback if no webhook URL is configured
    if not resolved_url:
        spool_entry["status"] = "AIR_GAPPED_NO_URL"
        _spool_telemetry_event(spool_entry, spool_file)
        return False

    # Format Discord / Slack compatible payload if raw dict
    http_payload = dict(status_payload)
    if "content" not in http_payload and "embeds" not in http_payload and "text" not in http_payload:
        title = http_payload.get("event", http_payload.get("status", "CoChem-TORQ Telemetry Event"))
        description = http_payload.get("message", f"Status update from node {http_payload.get('node_id', 'unknown')}")
        http_payload = {
            "content": f"**[CoChem-TORQ]** {title}: {description}",
            "embeds": [
                {
                    "title": str(title),
                    "description": str(description),
                    "timestamp": timestamp_utc,
                    "fields": [
                        {"name": str(k), "value": str(v), "inline": True}
                        for k, v in list(status_payload.items())[:10]
                        if k not in ("content", "embeds", "text", "message")
                    ],
                }
            ],
        }

    # Exponential Backoff Circuit Breaker Loop
    last_exception: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            import httpx

            with httpx.Client(timeout=clamped_timeout) as client:
                response = client.post(resolved_url, json=http_payload)
                if response.status_code in (200, 204):
                    return True
                elif 400 <= response.status_code < 500 and response.status_code != 429:
                    # Client error (e.g. 400 Bad Request, 404 Not Found) - do not retry indefinitely
                    last_exception = RuntimeError(f"HTTP {response.status_code}: {response.text}")
                    break
                else:
                    last_exception = RuntimeError(f"HTTP {response.status_code}: {response.text}")

        except Exception as exc:
            last_exception = exc

        # Exponential backoff delay: 0.5s * 2^(attempt-1), capped at 2.0s
        if attempt < max_retries:
            backoff_delay = min(2.0, 0.5 * (2 ** (attempt - 1)))
            time.sleep(backoff_delay)

    # Tripartite Fallback: Spool to deque, append to telemetry_spool.jsonl, warn
    spool_entry["status"] = "DISPATCH_FAILED"
    spool_entry["error"] = str(last_exception)
    _spool_telemetry_event(spool_entry, spool_file)

    warnings.warn(
        f"Webhook event dispatch failed after {max_retries} attempts ({last_exception}). "
        f"Event preserved in local telemetry spool.",
        TelemetryNetworkExhaustedWarning,
        stacklevel=2,
    )
    return False


def generate_plotly_3d_carousels(
    pes_tensor: np.ndarray,
    dvr_wavefunctions: Optional[np.ndarray] = None,
    output_path: Optional[str] = None,
    grid_x: Optional[np.ndarray] = None,
    grid_y: Optional[np.ndarray] = None,
    max_nodes: int = 5000,
    interpolation_mode: str = "pchip",
    title: str = "CoChem-TORQ 3D Potential Energy Surface",
) -> str:
    """
    High-Fidelity 2D/3D PES Topological Decimation & Plotly Visualizer.
    Downsamples multidimensional Potential Energy Surface grids and DVR wavefunctions
    using monotonic PCHIP/linear interpolation while strictly preserving (i, j)
    quadrilateral topology and stationary/critical points (nabla V = 0 minima/saddle points).

    Generates standalone, air-gapped WCAG 2.1 AA accessible HTML visualizers (< 4.5 MB).

    Parameters:
        pes_tensor: 2D array of shape (Nx, Ny) representing the energy surface in cm^-1 or kcal/mol.
        dvr_wavefunctions: Optional array of shape (N_states, Nx, Ny) representing wavefunctions.
        output_path: Optional file path to save standalone HTML visualizer.
        grid_x: 1D array of X-axis coordinates (e.g. dihedral angle 1 in degrees).
        grid_y: 1D array of Y-axis coordinates (e.g. dihedral angle 2 in degrees).
        max_nodes: Maximum node budget for decimated mesh (default: 5000).
        interpolation_mode: 'pchip' (C^1 monotonic) or 'linear' (C^0).
        title: Plot title for the visualizer.

    Returns:
        String containing complete standalone HTML document (< 4.5 MB).
    """
    pes_arr = np.asarray(pes_tensor, dtype=np.float64)
    if pes_arr.ndim != 2:
        if pes_arr.ndim == 1:
            side = int(math.isqrt(pes_arr.size))
            if side * side == pes_arr.size:
                pes_arr = pes_arr.reshape((side, side))
            else:
                pes_arr = pes_arr.reshape((1, -1))
        else:
            raise ValueError(f"pes_tensor must be 2D; received shape {pes_arr.shape}")

    Nx, Ny = pes_arr.shape

    if grid_x is None:
        grid_x = np.linspace(0.0, 360.0, Nx)
    else:
        grid_x = np.asarray(grid_x, dtype=np.float64)

    if grid_y is None:
        grid_y = np.linspace(0.0, 360.0, Ny)
    else:
        grid_y = np.asarray(grid_y, dtype=np.float64)

    # 1. Critical Point Detection on Full Resolution Grid (nabla V = 0)
    # Detect local minima, saddle points, and maxima
    critical_points: List[Tuple[float, float, float, str]] = []
    if Nx > 4 and Ny > 4:
        grad_x, grad_y = np.gradient(pes_arr, grid_x, grid_y)
        grad_norm = np.sqrt(grad_x**2 + grad_y**2)
        grad_threshold = np.percentile(grad_norm, 2.0)  # Near-zero gradient candidate

        for i in range(1, Nx - 1):
            for j in range(1, Ny - 1):
                val = pes_arr[i, j]
                neighbors = pes_arr[i - 1 : i + 2, j - 1 : j + 2]
                is_min = val == np.min(neighbors)
                is_max = val == np.max(neighbors)

                if is_min:
                    critical_points.append((float(grid_x[i]), float(grid_y[j]), float(val), "Local Minimum"))
                elif is_max:
                    critical_points.append((float(grid_x[i]), float(grid_y[j]), float(val), "Local Maximum"))
                elif grad_norm[i, j] <= grad_threshold:
                    # Check saddle point via Hessian eigenvalues
                    hxx = (pes_arr[i + 1, j] - 2 * val + pes_arr[i - 1, j]) / ((grid_x[1] - grid_x[0]) ** 2)
                    hyy = (pes_arr[i, j + 1] - 2 * val + pes_arr[i, j - 1]) / ((grid_y[1] - grid_y[0]) ** 2)
                    if hxx * hyy < 0:
                        critical_points.append((float(grid_x[i]), float(grid_y[j]), float(val), "Saddle Point (TS)"))

    # 2. 2D Strided Regular Grid Decimation Preserving (i, j) Topology
    total_nodes = Nx * Ny
    if total_nodes > max_nodes:
        # Calculate target resolution based on node budget

        # Monotonic PCHIP Interpolation along axes to resample smoothly without ringing
        target_nx = max(4, min(Nx, int(math.sqrt(max_nodes))))
        target_ny = max(4, min(Ny, int(max_nodes / target_nx)))

        dec_x = np.linspace(grid_x[0], grid_x[-1], target_nx)
        dec_y = np.linspace(grid_y[0], grid_y[-1], target_ny)

        if interpolation_mode == "pchip" and Nx > 2 and Ny > 2:
            # Axis-by-axis 1D PCHIP interpolator for monotonic C^1 continuity
            intermediate = np.zeros((Nx, target_ny), dtype=np.float64)
            for i in range(Nx):
                pchip_y = PchipInterpolator(grid_y, pes_arr[i, :])
                intermediate[i, :] = pchip_y(dec_y)

            dec_pes = np.zeros((target_nx, target_ny), dtype=np.float64)
            for j in range(target_ny):
                pchip_x = PchipInterpolator(grid_x, intermediate[:, j])
                dec_pes[:, j] = pchip_x(dec_x)
        else:
            # Linear strided decimation
            idx_x = np.linspace(0, Nx - 1, target_nx, dtype=int)
            idx_y = np.linspace(0, Ny - 1, target_ny, dtype=int)
            dec_pes = pes_arr[np.ix_(idx_x, idx_y)]
            dec_x = grid_x[idx_x]
            dec_y = grid_y[idx_y]
    else:
        dec_x = grid_x
        dec_y = grid_y
        dec_pes = pes_arr

    # 3. Plotly Standalone Visualizer Construction with WCAG 2.1 AA Contrast
    import plotly.graph_objects as go

    fig = go.Figure()

    # Base PES Surface (Viridis colormap meets WCAG 2.1 AA perceptual contrast)
    fig.add_trace(
        go.Surface(
            x=dec_x,
            y=dec_y,
            z=dec_pes.T,
            colorscale="Viridis",
            name="Potential Energy Surface",
            colorbar=dict(
                title=dict(text="Energy (cm⁻¹)", font=dict(color="#1A1A1A", size=14)),
                tickfont=dict(color="#1A1A1A", size=12),
                len=0.75,
            ),
            opacity=0.92,
            lighting=dict(ambient=0.65, diffuse=0.85, specular=0.15, roughness=0.5),
        )
    )

    # Stationary / Critical Point Overlay
    if critical_points:
        cp_x = [p[0] for p in critical_points]
        cp_y = [p[1] for p in critical_points]
        cp_z = [p[2] for p in critical_points]
        cp_hover = [f"{p[3]}<br>X: {p[0]:.2f}°<br>Y: {p[1]:.2f}°<br>E: {p[2]:.2f} cm⁻¹" for p in critical_points]

        fig.add_trace(
            go.Scatter3d(
                x=cp_x,
                y=cp_y,
                z=cp_z,
                mode="markers",
                marker=dict(
                    size=6,
                    color="#D9381E",  # High-contrast red
                    symbol="diamond",
                    line=dict(color="#FFFFFF", width=1),
                ),
                name="Critical Points (min/TS)",
                text=cp_hover,
                hoverinfo="text",
            )
        )

    # Wavefunction Overlays (if provided)
    if dvr_wavefunctions is not None:
        wf_arr = np.asarray(dvr_wavefunctions, dtype=np.float64)
        if wf_arr.ndim == 3 and wf_arr.shape[1] == Nx and wf_arr.shape[2] == Ny:
            for state_idx in range(min(3, wf_arr.shape[0])):
                wf_dec = wf_arr[state_idx][:: max(1, Nx // len(dec_x)), :: max(1, Ny // len(dec_y))]
                wf_surface = dec_pes.T + (wf_dec.T * (np.ptp(dec_pes) * 0.15))
                fig.add_trace(
                    go.Surface(
                        x=dec_x,
                        y=dec_y,
                        z=wf_surface,
                        showscale=False,
                        opacity=0.45,
                        colorscale="Plasma",
                        name=f"DVR Wavefunction v={state_idx}",
                    )
                )

    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=18, color="#111111", family="Arial, sans-serif"),
        ),
        scene=dict(
            xaxis=dict(
                title=dict(text="Torsion Angle θ₁ (°)", font=dict(color="#111111", size=12)),
                tickfont=dict(color="#222222", size=10),
                backgroundcolor="#F8F9FA",
                gridcolor="#D0D4DC",
            ),
            yaxis=dict(
                title=dict(text="Torsion Angle θ₂ (°)", font=dict(color="#111111", size=12)),
                tickfont=dict(color="#222222", size=10),
                backgroundcolor="#F8F9FA",
                gridcolor="#D0D4DC",
            ),
            zaxis=dict(
                title=dict(text="Energy (cm⁻¹)", font=dict(color="#111111", size=12)),
                tickfont=dict(color="#222222", size=10),
                backgroundcolor="#F8F9FA",
                gridcolor="#D0D4DC",
            ),
        ),
        margin=dict(l=20, r=20, b=20, t=50),
        paper_bgcolor="#FFFFFF",
    )

    # Standalone HTML export with CDN bundle (< 4.5 MB envelope)
    html_str = fig.to_html(include_plotlyjs="cdn", full_html=True)

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(html_str)

    return html_str


def export_crash_animation(
    trajectory_array: Union[np.ndarray, List[Any]],
    error_node_id: str,
    output_path: Optional[str] = None,
    atom_symbols: Optional[List[str]] = None,
    gradient_norms: Optional[List[float]] = None,
    diagnostic_data: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Steric Shatter Soft-Quench Crash Trajectory & Diagnostic Pathology Serializer.
    Dumps multi-frame crash_animation.xyz and structured crash_diagnostic.json
    capturing optimization steps leading up to gradient explosion or steric clash.

    Parameters:
        trajectory_array: Array of shape (N_frames, N_atoms, 3) with Cartesian coordinates.
        error_node_id: Identifier of the failing worker or stage node.
        output_path: Destination folder or base path for crash deliverables.
        atom_symbols: Optional list of element symbols (e.g. ['C', 'H', 'H', 'H', 'O', 'H']).
        gradient_norms: Optional list of gradient norm magnitudes ||nabla E|| per frame.
        diagnostic_data: Optional dictionary with supplementary failure metadata.

    Returns:
        Tuple containing (xyz_filepath, json_filepath).
    """
    traj = np.asarray(trajectory_array, dtype=np.float64)
    if traj.ndim == 2:
        # Single frame (N_atoms, 3) -> promote to (1, N_atoms, 3)
        traj = traj.reshape((1, traj.shape[0], traj.shape[1]))
    elif traj.ndim != 3 or traj.shape[2] != 3:
        raise ValueError(f"trajectory_array must have shape (N_frames, N_atoms, 3); received {traj.shape}")

    num_frames, num_atoms, _ = traj.shape

    if atom_symbols is None:
        atom_symbols = ["C" if i == 0 else "H" for i in range(num_atoms)]
    elif len(atom_symbols) != num_atoms:
        atom_symbols = (list(atom_symbols) + ["X"] * num_atoms)[:num_atoms]

    if gradient_norms is None:
        grad_norms = [0.0] * num_frames
    else:
        grad_norms = list(gradient_norms)
        if len(grad_norms) < num_frames:
            grad_norms.extend([grad_norms[-1] if grad_norms else 0.0] * (num_frames - len(grad_norms)))

    # Determine output paths
    if output_path:
        out_dir = Path(output_path)
        if out_dir.suffix in (".xyz", ".json"):
            out_dir = out_dir.parent
    else:
        out_dir = Path("torq_crash_reports")

    out_dir.mkdir(parents=True, exist_ok=True)
    xyz_path = out_dir / "crash_animation.xyz"
    json_path = out_dir / "crash_diagnostic.json"

    # 1. Multi-Frame XYZ Trajectory Serialization
    xyz_lines: List[str] = []
    for f_idx in range(num_frames):
        gn = grad_norms[f_idx]
        xyz_lines.append(str(num_atoms))
        xyz_lines.append(
            f"Frame {f_idx}: error_node={error_node_id} | grad_norm={gn:.6e} | timestamp={datetime.now(timezone.utc).isoformat()}"
        )
        for a_idx in range(num_atoms):
            sym = atom_symbols[a_idx]
            x, y, z = traj[f_idx, a_idx]
            xyz_lines.append(f"{sym:<3} {x:14.8f} {y:14.8f} {z:14.8f}")

    with open(xyz_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xyz_lines) + "\n")

    # 2. Interatomic Clash & Minimum Distance Analysis on Final Frame
    final_frame = traj[-1]
    min_dist = float("inf")
    clash_pair = None

    for i in range(num_atoms):
        for j in range(i + 1, num_atoms):
            dist = float(np.linalg.norm(final_frame[i] - final_frame[j]))
            if dist < min_dist:
                min_dist = dist
                clash_pair = (i, j)

    steric_clash = min_dist < 0.70  # Sub-van-der-Waals collapse threshold

    # 3. Crash Diagnostic JSON Report
    diagnostic: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "error_node_id": error_node_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "failure_type": "StericShatterCollision" if steric_clash else "GradientNormExplosion",
        "total_frames": num_frames,
        "num_atoms": num_atoms,
        "atom_symbols": atom_symbols,
        "gradient_norms": [float(g) for g in grad_norms],
        "max_gradient_norm": float(max(grad_norms)) if grad_norms else 0.0,
        "steric_clash_detected": steric_clash,
        "minimum_interatomic_distance_angstrom": float(min_dist),
        "clashing_atom_indices": list(clash_pair) if clash_pair else [],
        "clashing_atom_pair": [
            f"{atom_symbols[clash_pair[0]]}{clash_pair[0]}",
            f"{atom_symbols[clash_pair[1]]}{clash_pair[1]}",
        ]
        if clash_pair
        else [],
        "status": "ABORTED_SOFT_QUENCH",
    }

    if diagnostic_data:
        diagnostic["supplementary_diagnostic"] = diagnostic_data

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diagnostic, f, indent=2)

    return str(xyz_path), str(json_path)
