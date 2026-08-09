from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QGroupBox, QLabel
import pyvista as pv
from pyvistaqt import QtInteractor

class ToposTab(QWidget):
    """Combinatorial Engine (TOPOS) Structural Input & 3D Viewer Tab"""
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # Left panel: 3D Viewer
        viewer_group = QGroupBox("3D Molecular Viewer")
        viewer_layout = QVBoxLayout()
        self.plotter = QtInteractor(self)
        # Didactic: Draw a default sphere (representing an atom/molecule center)
        sphere = pv.Sphere()
        self.plotter.add_mesh(sphere, color="cyan")
        viewer_layout.addWidget(self.plotter.interactor)
        viewer_group.setLayout(viewer_layout)
        layout.addWidget(viewer_group, stretch=2)

        # Right panel: Controls
        control_group = QGroupBox("Conformational Engine")
        control_layout = QVBoxLayout()
        
        self.toggle_mmff94 = QCheckBox("Enable MMFF94 Pre-optimization")
        self.toggle_mmff94.setChecked(True)
        self.toggle_torsion = QCheckBox("Full Torsional Scan")
        
        # Toggles
        control_layout.addWidget(self.toggle_mmff94)
        control_layout.addWidget(self.toggle_torsion)
        
        # Action button
        self.btn_generate = QPushButton("Generate Conformers")
        control_layout.addWidget(self.btn_generate)
        
        # Didactic Tooltip as per requirements
        self.lbl_didactic = QLabel("Didactic Info: Torsional scans rotate bonds to explore Potential Energy Surfaces.")
        self.lbl_didactic.setWordWrap(True)
        control_layout.addStretch()
        control_layout.addWidget(self.lbl_didactic)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group, stretch=1)
