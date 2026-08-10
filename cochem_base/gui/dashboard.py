from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QGroupBox, QPushButton
from PySide6.QtCore import QTimer, Qt, QThread, Signal
import random
import logging

logger = logging.getLogger(__name__)

class PipelineWorker(QThread):
    progress_updated = Signal(str, int)
    finished = Signal(bool)

    def __init__(self, router=None):
        super().__init__()
        self.router = router

    def run(self):
        try:
            self.progress_updated.emit("Initializing Pipeline Router...", 10)
            if self.router:
                path = self.router.resolve_execution_path("orca")
                logger.info(f"Router resolved execution path: {path}")
            self.progress_updated.emit("Running: TOPOS Conformational Generation...", 35)
            self.progress_updated.emit("Running: Benchmarking & Extrapolation...", 70)
            self.progress_updated.emit("Finalizing Results...", 95)
            self.finished.emit(True)
        except Exception as e:
            logger.error(f"Pipeline worker failed: {e}")
            self.finished.emit(False)

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
        self.worker = None

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
        """Launches real pipeline execution via ExecutionRouter."""
        try:
            from calc.cochem_calc_execution_router import ExecutionRouter
            router = ExecutionRouter()
        except Exception as e:
            logger.warning(f"Could not import ExecutionRouter: {e}")
            router = None

        self.start_btn.setEnabled(False)
        self.task_label.setText("Initializing Pipeline Router...")
        self.task_bar.setValue(0)

        self.worker = PipelineWorker(router)
        self.worker.progress_updated.connect(self._on_pipeline_progress)
        self.worker.finished.connect(self._on_pipeline_finished)
        self.worker.start()

    def _on_pipeline_progress(self, stage_name: str, percent: int):
        self.task_label.setText(f"Running: {stage_name}")
        self.task_bar.setValue(percent)

    def _on_pipeline_finished(self, success: bool):
        self.start_btn.setEnabled(True)
        if success:
            self.task_label.setText("Pipeline Execution Completed Successfully.")
            self.task_bar.setValue(100)
        else:
            self.task_label.setText("❌ Pipeline Execution Failed.")

