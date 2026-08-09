from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGroupBox, QPushButton
from PySide6.QtCore import QTimer, Qt
import random

class DashboardTab(QWidget):
    """Home Dashboard / System Monitor (CoChem-BASE)"""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Hardware Utilization Group
        hw_group = QGroupBox("Real-time Hardware Utilization")
        hw_layout = QVBoxLayout()
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFormat("CPU: %p%")
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setFormat("GPU: %p%")
        self.ram_bar = QProgressBar()
        self.ram_bar.setFormat("RAM: %p%")
        
        hw_layout.addWidget(self.cpu_bar)
        hw_layout.addWidget(self.gpu_bar)
        hw_layout.addWidget(self.ram_bar)
        hw_group.setLayout(hw_layout)
        layout.addWidget(hw_group)

        # Master Task Queue Group
        queue_group = QGroupBox("Master Task Queue")
        queue_layout = QVBoxLayout()
        self.task_bar = QProgressBar()
        self.task_bar.setFormat("Pipeline Progress: %p%")
        self.task_label = QLabel("Idle")
        queue_layout.addWidget(self.task_label)
        queue_layout.addWidget(self.task_bar)
        queue_group.setLayout(queue_layout)
        layout.addWidget(queue_group)
        
        # Start Pipeline button
        self.start_btn = QPushButton("Start Pipeline")
        self.start_btn.clicked.connect(self.simulate_pipeline)
        layout.addWidget(self.start_btn)
        
        layout.addStretch()

        # Timer for simulated HW metrics
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_hw_metrics)
        self.timer.start(1000)

    def update_hw_metrics(self):
        """Query real system hardware metrics via psutil."""
        try:
            import psutil
            cpu_val = int(psutil.cpu_percent())
            ram_val = int(psutil.virtual_memory().percent)
        except Exception:
            cpu_val = 0
            ram_val = 0

        gpu_val = 0
        try:
            import torch
            if torch.cuda.is_available():
                gpu_val = int(torch.cuda.utilization_rate()) if hasattr(torch.cuda, "utilization_rate") else 0
        except Exception:
            gpu_val = 0

        self.cpu_bar.setValue(cpu_val)
        self.gpu_bar.setValue(gpu_val)
        self.ram_bar.setValue(ram_val)

    def simulate_pipeline(self):
        self.task_label.setText("Running: TOPOS Conformational Generation...")
        self.task_bar.setValue(25)
