import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

class TorqTab(QWidget):
    """Physics Configuration Panel & Quantum Resonance (CoChem-TORQ)"""
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        # Physics Configuration Panel
        config_group = QGroupBox("Physics Configuration: Classical vs. Quantum")
        config_layout = QVBoxLayout()

        # Threshold slider
        self.slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self.slider_threshold.setRange(0, 100)
        self.slider_threshold.setValue(50)

        # Labels for the slider
        lbl_layout = QHBoxLayout()
        lbl_layout.addWidget(QLabel("Classical Mechanics (MMFF94)"))
        lbl_layout.addStretch()
        lbl_layout.addWidget(QLabel("Quantum Mechanics (DFT/CCSD(T))"))

        # Value label
        self.lbl_value = QLabel("Treatment Threshold: 50%")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Didactic Math View
        self.lbl_didactic = QLabel("Didactic View: <i>H</i>&#770;&Psi; = <i>E</i>&Psi;")
        self.lbl_didactic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_didactic.setVisible(False)
        self.btn_didactic = QPushButton("Toggle Didactic Math View")
        self.btn_didactic.clicked.connect(self.toggle_didactic)

        # Academic Citation Generator
        self.lbl_citation = QLabel("Citation: [MISSING DATA]")
        self.lbl_citation.setStyleSheet("color: gray; font-size: 10px;")

        self.slider_threshold.valueChanged.connect(self.update_threshold_label)

        config_layout.addLayout(lbl_layout)
        config_layout.addWidget(self.slider_threshold)
        config_layout.addWidget(self.lbl_value)
        config_layout.addWidget(self.btn_didactic)
        config_layout.addWidget(self.lbl_didactic)
        config_layout.addWidget(self.lbl_citation)
        config_group.setLayout(config_layout)

        layout.addWidget(config_group)
        layout.addStretch()

        # Initialize labels
        self.update_threshold_label(50)

    def toggle_didactic(self) -> None:
        new_state = not self.lbl_didactic.isVisible()
        self.lbl_didactic.setVisible(new_state)
        logger.info(f"Toggled didactic view to: {new_state}")

    def update_threshold_label(self, value: int) -> None:
        self.lbl_value.setText(f"Treatment Threshold: {value}%")
        # Visual Theoretical Validation (Color Coding)
        if value < 30:
            color = "red"  # MMFF94 / Classical
            citation = "[D] Halgren, T. A. MMFF94. <i>J. Comput. Chem.</i> <b>1996</b>, 17, 490."
        elif value < 70:
            color = "orange"  # B3LYP-D3/D4 / DFT
            citation = "[D] Becke, A. D. <i>J. Chem. Phys.</i> <b>1993</b>, 98, 5648."
        else:
            color = "green"  # CCSD(T) / Ab Initio
            citation = "[D] Purvis, G. D.; Bartlett, R. J. <i>J. Chem. Phys.</i> <b>1982</b>, 76, 1910."

        self.lbl_value.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.lbl_citation.setText(f"Citation: {citation}")
        logger.debug(f"Threshold updated to {value}%. Set citation: {citation}")
