#!/usr/bin/env python3
"""CoChem-TORQ: Quantum Resonance & Torsional Optimization Subsystem.

Provides domain models, numerical constants, academic citation registry,
didactic mathematical formulations, background simulation worker (TorqWorker),
and the Qt-based configuration and trajectory panel (TorqTab).
"""

from __future__ import annotations

from enum import Enum
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from cochem_base.core.models import GeomTorqStage

logger = logging.getLogger(__name__)

# Physical & Numerical Conversion Constants
HARTREE_TO_KCAL = 627.5094740631
HARTREE_TO_EV = 27.211386245988
BOHR_TO_ANGSTROM = 0.529177210903

# Academic Citation Registry with Provenance Tags
ACADEMIC_CITATIONS: Dict[str, str] = {
    "MMFF94": "[M] Halgren, T. A. Merck molecular force field. I. J. Comput. Chem. 1996, 17, 490-519.",
    "B3LYP-D4": "[M] Becke, A. D. J. Chem. Phys. 1993, 98, 5648; Caldeweyher, E. et al. J. Chem. Phys. 2019, 150, 154122.",
    "wB97X-D4": "[M] Chai, J.-D.; Head-Gordon, M. Phys. Chem. Chem. Phys. 2008, 10, 6615; Caldeweyher, E. et al. 2019.",
    "PBE0-D4": "[M] Adamo, C.; Barone, V. J. Chem. Phys. 1999, 110, 6158; Caldeweyher, E. et al. 2019.",
    "DLPNO-CCSD(T)": "[D] Riplinger, C.; Neese, F. J. Chem. Phys. 2013, 138, 034106.",
    "CI-NEB": "[E] Henkelman, G.; Uberuaga, B. P.; Jonsson, H. J. Chem. Phys. 2000, 113, 9901-9904.",
    "RFO": "[M] Banerjee, A.; Adams, N.; Simons, J.; Shepard, R. J. Phys. Chem. 1985, 89, 52-57.",
    "BFGS": "[M] Fletcher, R. Practical Methods of Optimization; Wiley: New York, 1987.",
    "Davidson": "[M] Davidson, E. R. J. Comput. Phys. 1975, 17, 87-94.",
    "Lanczos": "[M] Lanczos, C. J. Res. Natl. Bur. Stand. 1950, 45, 255-282.",
    "Lindh": "[M] Lindh, R.; Bernhardsson, A.; Karlstrom, G.; Malmqvist, P.-A. Chem. Phys. Lett. 1995, 241, 423-428.",
    "InHess XTB2": "[M] Bannwarth, C.; Ehlert, S.; Grimme, S. J. Chem. Theory Comput. 2019, 15, 1652-1671.",
    "BSSE": "[M] Boys, S. F.; Bernardi, F. Mol. Phys. 1970, 19, 553-566.",
}

# Didactic Mathematical Formulations for Theoretical Reference
DIDACTIC_MATH_FORMULATIONS: Dict[str, Dict[str, str]] = {
    "RFO_Augmented_Hessian": {
        "title": "Rational Function Optimization (Augmented Hessian)",
        "latex": r"\begin{pmatrix} \mathbf{H} & \mathbf{g} \\ \mathbf{g}^T & 0 \end{pmatrix} \begin{pmatrix} \Delta \mathbf{x} \\ 1 \end{pmatrix} = \lambda \begin{pmatrix} \mathbf{S} & \mathbf{0} \\ \mathbf{0}^T & 1 \end{pmatrix} \begin{pmatrix} \Delta \mathbf{x} \\ 1 \end{pmatrix}",
        "html": "<h3>Rational Function Optimization (RFO)</h3><p>RFO augments the exact or quasi-Newton Hessian with the gradient vector to guarantee step boundedness and monotonic descent.</p>",
        "description": "Constructs an augmented (N+1)x(N+1) matrix eigenvalue problem ensuring robust step size control.",
        "method_matrix_rule": "MM-V4-OPT-001: RFO is mandatory for ground-state and transition state searches.",
    },
    "BFGS_Secant_Update": {
        "title": "BFGS Hessian Update with Powell Damping",
        "latex": r"\mathbf{H}_{k+1} = \mathbf{H}_k + \frac{\mathbf{y}_k \mathbf{y}_k^T}{\mathbf{y}_k^T \mathbf{s}_k} - \frac{\mathbf{H}_k \mathbf{s}_k \mathbf{s}_k^T \mathbf{H}_k}{\mathbf{s}_k^T \mathbf{H}_k \mathbf{s}_k}",
        "html": "<h3>BFGS Quasi-Newton Secant Update</h3><p>Maintains positive definiteness through symmetric rank-2 updates along the coordinate displacement vector.</p>",
        "description": "Updates the inverse or direct Hessian using step vectors s_k and gradient differences y_k.",
        "method_matrix_rule": "MM-V4-OPT-002: Hessian updating must preserve positive-definiteness on minima paths.",
    },
    "CI_NEB_Forces": {
        "title": "Climbing-Image Nudged Elastic Band (CI-NEB)",
        "latex": r"\mathbf{F}_{i}^{\text{CI}} = -\mathbf{\nabla} V(\mathbf{R}_i) + 2 \left( \mathbf{\nabla} V(\mathbf{R}_i) \cdot \mathbf{\hat{\tau}}_i \right) \mathbf{\hat{\tau}}_i + \mathbf{F}_i^{s \parallel}",
        "html": "<h3>Climbing-Image Nudged Elastic Band</h3><p>Inverts the parallel force component along the path tangent for the highest energy image to rigorously converge onto the saddle point.</p>",
        "description": "Drives the maximum energy bead directly up the MEP to find exact transition states.",
        "method_matrix_rule": "MM-V4-OPT-003: Transition state discovery requires CI-NEB or eigenvector following.",
    },
    "Krylov_Davidson_Lanczos": {
        "title": "Krylov Subspace Diagonalization (Davidson / Lanczos)",
        "latex": r"\mathcal{K}_m(\mathbf{H}, \mathbf{v}_1) = \text{span}\{\mathbf{v}_1, \mathbf{H}\mathbf{v}_1, \mathbf{H}^2\mathbf{v}_1, \dots, \mathbf{H}^{m-1}\mathbf{v}_1\}",
        "html": "<h3>Krylov Subspace Iterative Solvers</h3><p>Extracts lowest/negative eigenvalues without full O(N^3) matrix inversion, scaling to thousands of atoms.</p>",
        "description": "Iterative subspace projection for large-scale vibrational analysis and TS Hessian modes.",
        "method_matrix_rule": "MM-V4-OPT-004: Systems with > 100 atoms must use iterative Krylov diagonalizers.",
    },
    "InHess_Preconditioning": {
        "title": "Semi-empirical InHess Preconditioning",
        "latex": r"\mathbf{H}_0 = \mathbf{H}_{\text{GFN2-xTB}} \quad \text{or} \quad \mathbf{H}_0 = \mathbf{H}_{\text{Lindh}}",
        "html": "<h3>InHess Preconditioning</h3><p>Provides a chemically accurate initial Hessian from GFN2-xTB or Lindh empirical models, reducing DFT optimization cycles by 40-70%.</p>",
        "description": "Initializes optimization with semi-empirical force constants avoiding expensive DFT analytical Hessians.",
        "method_matrix_rule": "MM-V4-OPT-005: Never execute Calc_Hess true; use InHess XTB2 or Lindh.",
    },
    "Dynamic_Grid_Tightening": {
        "title": "Dynamic Grid Tightening Protocol",
        "latex": r"\text{Grid}(k) = \begin{cases} \text{defgrid1}, & \|\mathbf{g}_k\|_\infty > 1.0 \times 10^{-3} \\ \text{defgrid2}, & 3.0 \times 10^{-4} < \|\mathbf{g}_k\|_\infty \le 1.0 \times 10^{-3} \\ \text{defgrid3}, & \|\mathbf{g}_k\|_\infty \le 3.0 \times 10^{-4} \end{cases}",
        "html": "<h3>Dynamic DFT Grid Tightening</h3><p>Starts on coarse grids to rapidly traverse high-gradient regions, dynamically tightening to defgrid3 near convergence.</p>",
        "description": "Minimizes quadrature evaluation cost while guaranteeing grid-independent final energies.",
        "method_matrix_rule": "MM-V4-OPT-006: Start on defgrid1 and finish on defgrid3 near minimum.",
    },
    "Weak_Complex_Convergence": {
        "title": "Non-Covalent Weak Complex Convergence Criteria",
        "latex": r"\text{TolMaxG} \le 1.0 \times 10^{-5} \text{ a.u.}, \quad \text{TolRMSG} \le 5.0 \times 10^{-6} \text{ a.u.}, \quad \Delta E_{\text{BSSE}} = E_{\text{AB}}^{\text{mono}} - E_{\text{A(B)}}^{\text{dimer}} - E_{\text{B(A)}}^{\text{dimer}}",
        "html": "<h3>Weak Complex Convergence</h3><p>Tightens force thresholds by 30x to prevent premature convergence on shallow intermolecular flat PES plateaus.</p>",
        "description": "Strict criteria and counterpoise BSSE corrections for intermolecular adducts and dimers.",
        "method_matrix_rule": "MM-V4-OPT-007: Weak complex calculations require TolMaxG <= 1e-5 and BSSE.",
    },
}


class OptimizationType(str, Enum):
    MIN = "Min"
    TS = "TS"
    CI_NEB = "CI-NEB"
    IRC = "IRC"
    SCAN = "Scan"


class HessianDiagonalizer(str, Enum):
    DENSE = "Dense"
    DAVIDSON = "Davidson"
    LANCZOS = "Lanczos"


class HessianPreconditioner(str, Enum):
    IN_HESS_XTB2 = "InHess XTB2"
    LINDH = "Lindh"


class DispersionType(str, Enum):
    D4 = "D4"
    D3 = "D3"
    D3BJ = "D3BJ"
    D4BJ = "D4BJ"
    NONE = "None"


class GridLevel(str, Enum):
    DEFGRID1 = "defgrid1"
    DEFGRID2 = "defgrid2"
    DEFGRID3 = "defgrid3"


class CoordinateType(str, Enum):
    DIHEDRAL = "Dihedral"
    ANGLE = "Angle"
    DISTANCE = "Distance"


class ConvergenceCriteria(BaseModel):
    """Pydantic model for geometric optimization convergence thresholds."""

    model_config = ConfigDict(extra="allow")

    tol_e: float = 1.0e-6
    tol_max_g: float = 3.0e-4
    tol_rms_g: float = 1.0e-4
    tol_max_x: float = 1.8e-3
    tol_rms_x: float = 6.0e-4
    max_step: float = 0.1
    max_iter: int = 300
    weak_complex_mode: bool = False
    bsse_correction: bool = False

    @model_validator(mode="after")
    def _auto_tighten(self) -> ConvergenceCriteria:
        if self.weak_complex_mode:
            if self.tol_max_g > 1.0e-5:
                self.tol_max_g = 1.0e-5
            if self.tol_rms_g > 5.0e-6:
                self.tol_rms_g = 5.0e-6
            self.bsse_correction = True
        return self

    def apply_weak_complex_preset(self) -> ConvergenceCriteria:
        """Returns a new ConvergenceCriteria instance with weak-complex invariants applied."""
        return ConvergenceCriteria(
            tol_e=self.tol_e,
            tol_max_g=1.0e-5,
            tol_rms_g=5.0e-6,
            tol_max_x=self.tol_max_x,
            tol_rms_x=self.tol_rms_x,
            max_step=self.max_step,
            max_iter=500,
            weak_complex_mode=True,
            bsse_correction=True,
        )

    def is_step_converged(
        self, delta_e: float, max_g: float, rms_g: float, max_x: float, rms_x: float
    ) -> bool:
        """Evaluates whether all convergence criteria are satisfied."""
        return (
            abs(delta_e) <= self.tol_e
            and max_g <= self.tol_max_g
            and rms_g <= self.tol_rms_g
            and max_x <= self.tol_max_x
            and rms_x <= self.tol_rms_x
        )


class ScanParameters(BaseModel):
    """Parameters for 1D coordinate potential energy surface scanning."""

    model_config = ConfigDict(extra="allow")

    coordinate_type: str = "Dihedral"
    atom_indices: List[int] = Field(..., min_length=2)
    start_val: float = 0.0
    end_val: float = 180.0
    steps: int = 18

    @field_validator("coordinate_type")
    @classmethod
    def check_coordinate_type(cls, v: str) -> str:
        valid = [c.value for c in CoordinateType]
        if v not in valid:
            raise ValueError(f"coordinate_type must be one of {valid}")
        return v

    @field_validator("atom_indices")
    @classmethod
    def check_atom_indices(cls, v: List[int]) -> List[int]:
        if not v or any(idx < 1 for idx in v):
            raise ValueError("atom_indices must contain 1-based positive integers")
        return v

    @property
    def step_size(self) -> float:
        return (self.end_val - self.start_val) / max(self.steps, 1)

    def to_geom_scan_line(self) -> str:
        """Converts to ORCA %geom Scan command line syntax (0-indexed)."""
        zero_idx = " ".join(str(i - 1) for i in self.atom_indices)
        prefix_map = {"Dihedral": "D", "Angle": "A", "Distance": "B"}
        p = prefix_map.get(self.coordinate_type, "D")
        return f"{p} {zero_idx} = {self.start_val:.4f}, {self.end_val:.4f}, {self.steps}"


class TorqOptimizationConfig(BaseModel):
    """Master configuration model for CoChem-TORQ optimizations."""

    model_config = ConfigDict(extra="allow")

    opt_type: str = "Min"
    method_string: str = "B3LYP-D4/def2-TZVP"
    dispersion_correction: str = "D4"
    in_hess: str = "InHess XTB2"
    hess_diag: str = "Dense"
    grid_start: str = "defgrid1"
    grid_final: str = "defgrid3"
    max_cycles: int = 300
    trust_radius: float = 0.1
    convergence: ConvergenceCriteria = Field(default_factory=ConvergenceCriteria)
    scan_params: Optional[ScanParameters] = None

    @field_validator("in_hess")
    @classmethod
    def check_in_hess(cls, v: str) -> str:
        if "calc_hess true" in v.lower():
            raise ValueError("Calc_Hess true is strictly prohibited. Use InHess XTB2 or Lindh.")
        return v

    def to_geom_block(self) -> str:
        """Generates the compliant ORCA %geom block string."""
        in_hess_tag = "InHess_XTB2" if "xtb" in self.in_hess.lower() else "Lindh"
        lines = [
            "%geom",
            f"  MaxIter {self.max_cycles}",
            f"  InHess {in_hess_tag}",
            "  Calc_Hess false",
            "  Step RFO",
            f"  TolMaxG {self.convergence.tol_max_g:.4e}",
            f"  TolRMSG {self.convergence.tol_rms_g:.4e}",
            f"  TolMaxD {self.convergence.tol_max_x:.4e}",
            f"  TolRMSD {self.convergence.tol_rms_x:.4e}",
            f"  TolE {self.convergence.tol_e:.4e}",
        ]

        if self.opt_type == "TS":
            lines.append("  TS true")
            lines.append(f"  HessDiag {self.hess_diag}")
        elif self.opt_type == "CI-NEB":
            lines.append("  NEB")
            lines.append("    CI true")
            lines.append("    NImages 8")
            lines.append("  end")
        elif self.opt_type == "Scan" and self.scan_params:
            lines.append("  Scan")
            lines.append(f"    {self.scan_params.to_geom_scan_line()}")
            lines.append("  end")
        elif self.opt_type == "IRC":
            lines.append("  IRC")
            lines.append("    Direction Both")
            lines.append("  end")

        lines.append("end")
        return "\n".join(lines)

    def to_geom_torq_stage(self) -> GeomTorqStage:
        """Bridges configuration into core GeomTorqStage schema."""
        return GeomTorqStage(
            dispersion_correction=self.dispersion_correction,
            hessian_preconditioner=self.in_hess,
            grid_start=self.grid_start,
            grid_final=self.grid_final,
        )


class OptimizationStepRecord(BaseModel):
    """Pydantic model representing a single step in a geometry optimization trajectory."""

    model_config = ConfigDict(extra="allow")

    step: int
    energy_hartree: float
    delta_e_kcal: float
    max_gradient: float
    rms_gradient: float
    max_displacement: float
    rms_displacement: float
    step_type: str = "RFO"
    is_converged: bool = False
    grid_level: str = "defgrid1"
    timestamp: float = Field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TorqWorker(QThread):
    """Background computation worker for simulating or monitoring optimization trajectories."""

    progress_updated = Signal(int, int, str)
    step_completed = Signal(dict)
    optimization_finished = Signal(dict)
    log_emitted = Signal(str, str)

    def __init__(
        self,
        config: TorqOptimizationConfig,
        step_delay_ms: int = 100,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.step_delay_ms = step_delay_ms
        self._stop_requested = False
        self.step_records: List[OptimizationStepRecord] = []

    def request_stop(self) -> None:
        self._stop_requested = True

    def is_cancelled(self) -> bool:
        return self._stop_requested

    def run(self) -> None:
        self._stop_requested = False
        self.step_records.clear()
        self.log_emitted.emit("INFO", f"Starting TorqWorker with method {self.config.method_string}...")

        base_energy = -154.2800000
        current_g = 0.025000
        current_grid = self.config.grid_start

        # Step 0 initial point
        rec0 = OptimizationStepRecord(
            step=0,
            energy_hartree=base_energy,
            delta_e_kcal=0.0,
            max_gradient=current_g,
            rms_gradient=current_g * 0.45,
            max_displacement=0.045000,
            rms_displacement=0.021000,
            step_type="Initial",
            is_converged=False,
            grid_level=current_grid,
        )
        self.step_records.append(rec0)
        self.step_completed.emit(rec0.to_dict())

        if self._stop_requested:
            self.log_emitted.emit("WARNING", "TorqWorker cancelled before iteration loop.")
            return

        max_steps = min(self.config.max_cycles, 25)
        for s in range(1, max_steps + 1):
            if self._stop_requested:
                self.log_emitted.emit("WARNING", f"TorqWorker cancelled at step {s}.")
                break

            if self.step_delay_ms > 0:
                time.sleep(self.step_delay_ms / 1000.0)

            # Simulated physical descent
            decay_factor = 0.75 ** s
            current_g = max(0.00005, 0.025000 * decay_factor)
            energy_drop = 0.005000 * decay_factor
            base_energy -= energy_drop
            delta_kcal = -energy_drop * HARTREE_TO_KCAL

            # Dynamic grid tightening
            if current_g <= 3.0e-4:
                current_grid = self.config.grid_final
            elif current_g <= 1.0e-3:
                current_grid = GridLevel.DEFGRID2.value

            is_conv = current_g <= self.config.convergence.tol_max_g

            rec = OptimizationStepRecord(
                step=s,
                energy_hartree=round(base_energy, 7),
                delta_e_kcal=round(delta_kcal, 4),
                max_gradient=round(current_g, 6),
                rms_gradient=round(current_g * 0.42, 6),
                max_displacement=round(current_g * 1.5, 6),
                rms_displacement=round(current_g * 0.6, 6),
                step_type="RFO",
                is_converged=is_conv,
                grid_level=current_grid,
            )
            self.step_records.append(rec)
            self.step_completed.emit(rec.to_dict())
            self.progress_updated.emit(s, max_steps, f"Step {s}/{max_steps} ({current_grid})")

            if is_conv:
                self.log_emitted.emit("SUCCESS", f"Optimization converged in {s} steps at {current_grid}.")
                break

        summary = {
            "converged": any(r.is_converged for r in self.step_records),
            "total_steps": len(self.step_records) - 1,
            "final_energy_hartree": self.step_records[-1].energy_hartree if self.step_records else 0.0,
            "final_grid": current_grid,
        }
        self.optimization_finished.emit(summary)


class TorqTab(QWidget):
    """Physics Configuration Panel & Quantum Resonance (CoChem-TORQ)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.step_records: List[Dict[str, Any]] = []
        self.worker: Optional[TorqWorker] = None

        layout = QVBoxLayout(self)

        # Top Preset Bar
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("<b>Method Matrix Presets:</b>"))
        self.cbo_preset = QComboBox()
        self.cbo_preset.addItems([
            "Standard Ground State Minimum (RFO / InHess XTB2)",
            "Weak Complex (Non-Covalent / TolMaxG 1e-5)",
            "Transition State Search (EVF / CI-NEB)",
            "Relaxed PES Scan (Dihedral / Angle / Distance)",
        ])
        self.cbo_preset.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.cbo_preset)
        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_reset.clicked.connect(self.reset_defaults)
        preset_layout.addWidget(self.btn_reset)
        layout.addLayout(preset_layout)

        # Configuration Panel
        config_group = QGroupBox("Physics Configuration: Classical vs. Quantum")
        config_layout = QVBoxLayout()

        self.slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self.slider_threshold.setRange(0, 100)
        self.slider_threshold.setValue(50)
        self.slider_threshold.valueChanged.connect(self.update_threshold_label)

        lbl_layout = QHBoxLayout()
        lbl_layout.addWidget(QLabel("Classical Mechanics (MMFF94)"))
        lbl_layout.addStretch()
        lbl_layout.addWidget(QLabel("Quantum Mechanics (DFT/CCSD(T))"))

        self.lbl_value = QLabel("Treatment Threshold: 50%")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_citation = QLabel(ACADEMIC_CITATIONS["B3LYP-D4"])
        self.lbl_citation.setStyleSheet("color: #475569; font-size: 11px; font-style: italic;")

        config_layout.addLayout(lbl_layout)
        config_layout.addWidget(self.slider_threshold)
        config_layout.addWidget(self.lbl_value)
        config_layout.addWidget(self.lbl_citation)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Settings Controls Grid
        settings_group = QGroupBox("Electronic Structure & Optimization Parameters")
        settings_layout = QHBoxLayout()

        col1 = QVBoxLayout()
        col1.addWidget(QLabel("Optimization Type:"))
        self.cbo_opt_type = QComboBox()
        self.cbo_opt_type.addItems([e.value for e in OptimizationType])
        self.cbo_opt_type.currentTextChanged.connect(self._on_opt_type_changed)
        col1.addWidget(self.cbo_opt_type)

        col1.addWidget(QLabel("Hessian Preconditioner:"))
        self.cbo_in_hess = QComboBox()
        self.cbo_in_hess.addItems([e.value for e in HessianPreconditioner])
        self.cbo_in_hess.currentTextChanged.connect(self._update_geom_preview)
        col1.addWidget(self.cbo_in_hess)

        col1.addWidget(QLabel("Hessian Diagonalizer:"))
        self.cbo_hess_diag = QComboBox()
        self.cbo_hess_diag.addItems([e.value for e in HessianDiagonalizer])
        col1.addWidget(self.cbo_hess_diag)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("Dispersion Correction:"))
        self.cbo_dispersion = QComboBox()
        self.cbo_dispersion.addItems([e.value for e in DispersionType])
        col2.addWidget(self.cbo_dispersion)

        col2.addWidget(QLabel("Initial Grid:"))
        self.cbo_grid_start = QComboBox()
        self.cbo_grid_start.addItems([e.value for e in GridLevel])
        col2.addWidget(self.cbo_grid_start)

        col2.addWidget(QLabel("Final Grid:"))
        self.cbo_grid_final = QComboBox()
        self.cbo_grid_final.addItems([e.value for e in GridLevel])
        self.cbo_grid_final.setCurrentText("defgrid3")
        col2.addWidget(self.cbo_grid_final)

        col3 = QVBoxLayout()
        col3.addWidget(QLabel("Trust Radius (Max Step):"))
        self.spn_trust_radius = QDoubleSpinBox()
        self.spn_trust_radius.setRange(0.01, 1.0)
        self.spn_trust_radius.setSingleStep(0.02)
        self.spn_trust_radius.setValue(0.10)
        col3.addWidget(self.spn_trust_radius)

        col3.addWidget(QLabel("Max Cycles:"))
        self.spn_max_cycles = QSpinBox()
        self.spn_max_cycles.setRange(10, 2000)
        self.spn_max_cycles.setValue(300)
        col3.addWidget(self.spn_max_cycles)

        col3.addWidget(QLabel("TolMaxG (a.u.):"))
        self.spn_tol_max_g = QDoubleSpinBox()
        self.spn_tol_max_g.setDecimals(6)
        self.spn_tol_max_g.setRange(1.0e-7, 1.0e-2)
        self.spn_tol_max_g.setValue(3.0e-4)
        col3.addWidget(self.spn_tol_max_g)

        col4 = QVBoxLayout()
        self.chk_weak_complex = QCheckBox("Weak Complex Mode")
        self.chk_weak_complex.toggled.connect(self._on_weak_complex_toggled)
        col4.addWidget(self.chk_weak_complex)

        self.chk_bsse = QCheckBox("BSSE Correction")
        col4.addWidget(self.chk_bsse)

        self.chk_rfo_damping = QCheckBox("RFO Step Damping")
        self.chk_rfo_damping.setChecked(True)
        col4.addWidget(self.chk_rfo_damping)

        settings_layout.addLayout(col1)
        settings_layout.addLayout(col2)
        settings_layout.addLayout(col3)
        settings_layout.addLayout(col4)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Scan Group (Hidden by default)
        self.scan_group = QGroupBox("Coordinate Scan Parameters")
        scan_layout = QHBoxLayout()
        self.cbo_scan_type = QComboBox()
        self.cbo_scan_type.addItems([e.value for e in CoordinateType])
        scan_layout.addWidget(QLabel("Type:"))
        scan_layout.addWidget(self.cbo_scan_type)
        self.scan_group.setLayout(scan_layout)
        self.scan_group.setVisible(False)
        layout.addWidget(self.scan_group)

        # Didactic Math Section
        didactic_box = QGroupBox("Didactic Mathematical Formulations")
        didactic_layout = QVBoxLayout()

        d_head = QHBoxLayout()
        self.btn_didactic = QPushButton("Toggle Didactic Math View")
        self.btn_didactic.clicked.connect(self.toggle_didactic)
        d_head.addWidget(self.btn_didactic)

        self.cbo_didactic_topic = QComboBox()
        self.cbo_didactic_topic.addItems(list(DIDACTIC_MATH_FORMULATIONS.keys()))
        self.cbo_didactic_topic.currentTextChanged.connect(self._on_didactic_topic_changed)
        d_head.addWidget(self.cbo_didactic_topic)
        didactic_layout.addLayout(d_head)

        self.lbl_didactic = QLabel("Didactic View: <i>H</i>&#770;&Psi; = <i>E</i>&Psi;")
        self.lbl_didactic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_didactic.setVisible(False)
        didactic_layout.addWidget(self.lbl_didactic)

        self.txt_didactic_viewer = QTextBrowser()
        self.txt_didactic_viewer.setHtml(DIDACTIC_MATH_FORMULATIONS["RFO_Augmented_Hessian"]["html"])
        self.txt_didactic_viewer.setMaximumHeight(120)
        self.txt_didactic_viewer.setVisible(False)
        didactic_layout.addWidget(self.txt_didactic_viewer)

        didactic_box.setLayout(didactic_layout)
        layout.addWidget(didactic_box)

        # KPI Header Cards
        kpi_layout = QHBoxLayout()
        self.lbl_kpi_status = QLabel("<b>Status:</b> IDLE (defgrid1)")
        self.lbl_kpi_energy = QLabel("<b>Energy:</b> -154.280000 Eh")
        self.lbl_kpi_delta_e = QLabel("<b>Delta E:</b> 0.000 kcal/mol")
        self.lbl_kpi_max_g = QLabel("<b>Max |G|:</b> 0.025000 a.u.")
        kpi_layout.addWidget(self.lbl_kpi_status)
        kpi_layout.addWidget(self.lbl_kpi_energy)
        kpi_layout.addWidget(self.lbl_kpi_delta_e)
        kpi_layout.addWidget(self.lbl_kpi_max_g)
        layout.addLayout(kpi_layout)

        # Trajectory Table & %geom Preview Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table_trajectory = QTableWidget()
        headers = ["Step", "Energy (Eh)", "Delta E (kcal)", "Max |G|", "RMS |G|", "Max |D|", "RMS |D|", "Type", "Grid", "Converged"]
        self.table_trajectory.setColumnCount(len(headers))
        self.table_trajectory.setHorizontalHeaderLabels(headers)
        self.table_trajectory.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.table_trajectory)

        self.txt_geom_preview = QPlainTextEdit()
        self.txt_geom_preview.setReadOnly(True)
        self.txt_geom_preview.setMaximumWidth(320)
        splitter.addWidget(self.txt_geom_preview)

        layout.addWidget(splitter)

        # Export & Action Buttons
        btn_bar = QHBoxLayout()
        self.btn_export_geom = QPushButton("Export %geom Block")
        self.btn_export_geom.clicked.connect(lambda: self.export_geom_block())
        self.btn_export_json = QPushButton("Export Config JSON")
        self.btn_export_json.clicked.connect(lambda: self.export_config_json())
        self.btn_export_csv = QPushButton("Export Trajectory CSV")
        self.btn_export_csv.clicked.connect(lambda: self.export_trajectory_csv())

        btn_bar.addWidget(self.btn_export_geom)
        btn_bar.addWidget(self.btn_export_json)
        btn_bar.addWidget(self.btn_export_csv)
        layout.addLayout(btn_bar)

        self._update_geom_preview()

    def update_threshold_label(self, val: Optional[int] = None) -> None:
        v = self.slider_threshold.value() if val is None else val
        self.lbl_value.setText(f"Treatment Threshold: {v}%")
        if v < 30:
            self.lbl_citation.setText(f"Citation: {ACADEMIC_CITATIONS['MMFF94']}")
        elif v <= 70:
            self.lbl_citation.setText(f"Citation: {ACADEMIC_CITATIONS['B3LYP-D4']}")
        else:
            self.lbl_citation.setText(f"Citation: {ACADEMIC_CITATIONS['DLPNO-CCSD(T)']}")

    def toggle_didactic(self) -> None:
        vis = not self.lbl_didactic.isVisible()
        self.lbl_didactic.setVisible(vis)
        self.txt_didactic_viewer.setVisible(vis)

    def _on_didactic_topic_changed(self, topic: str) -> None:
        if topic in DIDACTIC_MATH_FORMULATIONS:
            self.txt_didactic_viewer.setHtml(DIDACTIC_MATH_FORMULATIONS[topic]["html"])

    def _on_opt_type_changed(self, opt_type: str) -> None:
        self.scan_group.setVisible(opt_type == "Scan")
        self._update_geom_preview()

    def _on_weak_complex_toggled(self, checked: bool) -> None:
        if checked:
            self.spn_tol_max_g.setValue(1.0e-5)
            self.chk_bsse.setChecked(True)
        else:
            self.spn_tol_max_g.setValue(3.0e-4)
        self._update_geom_preview()

    def _on_preset_selected(self, idx: int) -> None:
        preset_name = self.cbo_preset.currentText()
        self.apply_preset(preset_name)

    def apply_preset(self, preset_name: str) -> None:
        if "Weak Complex" in preset_name:
            self.chk_weak_complex.setChecked(True)
            self.chk_bsse.setChecked(True)
            self.spn_tol_max_g.setValue(1.0e-5)
            self.cbo_didactic_topic.setCurrentText("Weak_Complex_Convergence")
        elif "Transition State" in preset_name:
            self.cbo_opt_type.setCurrentText("TS")
            self.cbo_hess_diag.setCurrentText("Davidson")
            self.chk_rfo_damping.setChecked(True)
            self.cbo_didactic_topic.setCurrentText("Krylov_Davidson_Lanczos")
        elif "Relaxed PES" in preset_name:
            self.cbo_opt_type.setCurrentText("Scan")
            self.scan_group.setVisible(True)
        self._update_geom_preview()

    def reset_defaults(self) -> None:
        self.cbo_opt_type.setCurrentText("Min")
        self.cbo_in_hess.setCurrentText("InHess XTB2")
        self.cbo_hess_diag.setCurrentText("Dense")
        self.cbo_dispersion.setCurrentText("D4")
        self.cbo_grid_start.setCurrentText("defgrid1")
        self.cbo_grid_final.setCurrentText("defgrid3")
        self.spn_trust_radius.setValue(0.10)
        self.spn_max_cycles.setValue(300)
        self.spn_tol_max_g.setValue(3.0e-4)
        self.chk_weak_complex.setChecked(False)
        self.chk_bsse.setChecked(False)
        self.scan_group.setVisible(False)
        self._update_geom_preview()

    def get_config(self) -> TorqOptimizationConfig:
        conv = ConvergenceCriteria(
            tol_max_g=self.spn_tol_max_g.value(),
            max_iter=self.spn_max_cycles.value(),
            max_step=self.spn_trust_radius.value(),
            weak_complex_mode=self.chk_weak_complex.isChecked(),
            bsse_correction=self.chk_bsse.isChecked(),
        )
        scan_p = None
        if self.cbo_opt_type.currentText() == "Scan":
            scan_p = ScanParameters(
                coordinate_type=self.cbo_scan_type.currentText(),
                atom_indices=[1, 2, 3, 4],
                start_val=0.0,
                end_val=180.0,
                steps=18,
            )

        return TorqOptimizationConfig(
            opt_type=self.cbo_opt_type.currentText(),
            in_hess=self.cbo_in_hess.currentText(),
            hess_diag=self.cbo_hess_diag.currentText(),
            dispersion_correction=self.cbo_dispersion.currentText(),
            grid_start=self.cbo_grid_start.currentText(),
            grid_final=self.cbo_grid_final.currentText(),
            max_cycles=self.spn_max_cycles.value(),
            trust_radius=self.spn_trust_radius.value(),
            convergence=conv,
            scan_params=scan_p,
        )

    def apply_config(self, cfg: TorqOptimizationConfig) -> None:
        self.cbo_opt_type.setCurrentText(cfg.opt_type)
        self.cbo_in_hess.setCurrentText(cfg.in_hess)
        self.cbo_hess_diag.setCurrentText(cfg.hess_diag)
        self.cbo_dispersion.setCurrentText(cfg.dispersion_correction)
        self.cbo_grid_start.setCurrentText(cfg.grid_start)
        self.cbo_grid_final.setCurrentText(cfg.grid_final)
        self.spn_max_cycles.setValue(cfg.max_cycles)
        self.spn_trust_radius.setValue(cfg.trust_radius)
        self.spn_tol_max_g.setValue(cfg.convergence.tol_max_g)
        self.chk_weak_complex.setChecked(cfg.convergence.weak_complex_mode)
        self.chk_bsse.setChecked(cfg.convergence.bsse_correction)
        self._update_geom_preview()

    def to_geom_torq_stage(self) -> GeomTorqStage:
        return self.get_config().to_geom_torq_stage()

    def _update_geom_preview(self) -> None:
        cfg = self.get_config()
        self.txt_geom_preview.setPlainText(cfg.to_geom_block())

    def on_worker_step(self, step_dict: Dict[str, Any]) -> None:
        self.step_records.append(step_dict)
        row = self.table_trajectory.rowCount()
        self.table_trajectory.insertRow(row)

        vals = [
            str(step_dict.get("step", row)),
            f"{step_dict.get('energy_hartree', 0.0):.6f}",
            f"{step_dict.get('delta_e_kcal', 0.0):.3f}",
            f"{step_dict.get('max_gradient', 0.0):.6f}",
            f"{step_dict.get('rms_gradient', 0.0):.6f}",
            f"{step_dict.get('max_displacement', 0.0):.6f}",
            f"{step_dict.get('rms_displacement', 0.0):.6f}",
            str(step_dict.get("step_type", "RFO")),
            str(step_dict.get("grid_level", "defgrid1")),
            "YES" if step_dict.get("is_converged") else "NO",
        ]
        for col, v in enumerate(vals):
            self.table_trajectory.setItem(row, col, QTableWidgetItem(v))

        self.lbl_kpi_energy.setText(f"<b>Energy:</b> {step_dict.get('energy_hartree', 0.0):.6f} Eh")
        self.lbl_kpi_delta_e.setText(f"<b>Delta E:</b> {step_dict.get('delta_e_kcal', 0.0):.3f} kcal/mol")
        self.lbl_kpi_max_g.setText(f"<b>Max |G|:</b> {step_dict.get('max_gradient', 0.0):.6f} a.u.")
        grid = step_dict.get("grid_level", "defgrid1")
        self.lbl_kpi_status.setText(f"<b>Status:</b> IN PROGRESS ({grid})")

    def on_worker_finished(self, summary: Dict[str, Any]) -> None:
        grid = summary.get("final_grid", "defgrid3")
        status_text = "CONVERGED" if summary.get("converged") else "UNCONVERGED"
        self.lbl_kpi_status.setText(f"<b>Status:</b> {status_text} ({grid})")

    def reset_trajectory(self) -> None:
        self.table_trajectory.setRowCount(0)
        self.step_records.clear()
        self.lbl_kpi_status.setText("<b>Status:</b> IDLE (defgrid1)")

    def export_geom_block(self, file_path: Optional[Path] = None) -> str:
        text = self.get_config().to_geom_block()
        if file_path:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return text

    def export_config_json(self, file_path: Optional[Path] = None) -> str:
        text = self.get_config().model_dump_json(indent=2)
        if file_path:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return text

    def export_trajectory_csv(self, file_path: Optional[Path] = None) -> str:
        lines = ["Step,Energy_Hartree,Delta_E_kcal,Max_Gradient,RMS_Gradient,Max_Displacement,RMS_Displacement,Step_Type,Grid_Level,Is_Converged"]
        for s in self.step_records:
            lines.append(
                f"{s.get('step')},{s.get('energy_hartree')},{s.get('delta_e_kcal')},"
                f"{s.get('max_gradient')},{s.get('rms_gradient')},"
                f"{s.get('max_displacement')},{s.get('rms_displacement')},"
                f"{s.get('step_type')},{s.get('grid_level')},{s.get('is_converged')}"
            )
        text = "\n".join(lines) + "\n"
        if file_path:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return text

    def closeEvent(self, event: Any) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(2000)
        super().closeEvent(event)
