import logging
import sys
from pathlib import Path
from typing import Optional

import psutil

try:
    import torch
except ImportError:
    torch = None

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QGroupBox, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.config_loader import get_artifact_dir

logger = logging.getLogger(__name__)


class PipelineWorker(QThread):
    progress_updated = Signal(str, int)
    finished = Signal(bool)

    def __init__(self, router: ExecutionRouter) -> None:
        super().__init__()
        self.router = router

    def run(self) -> None:
        self.progress_updated.emit("Initializing Execution Router & Running Stage 1 Setup...", 10)
        
        # Eliminate mocked data/stub logic. We must run a real task constraint.
        # Run cochem_setup_1_sys.py as the real initial pipeline task.
        cmd = f'"{sys.executable}" -m calc.cochem_setup_1_sys'
        cwd = str(get_artifact_dir())
        
        # Router dispatch handles timeouts and executions without swallowing them blindly.
        exit_code = self.router.route_job("default", cmd, cwd=cwd, job_name="cochem_pipeline_stage1")
        
        if exit_code == 0:
            self.progress_updated.emit("Stage 1 Setup Complete. 11-Arrow Pipeline Handoff Required.", 50)
            # The rest of the pipeline is currently unimplemented. 
            # We abort here rather than mocking the remaining steps.
            logger.error("[HARD_ABORT: PHYSICS WALL] 11-Arrow Canonical Pipeline not implemented. Handoff to cochem-coder required.")
            self.finished.emit(False)
        else:
            self.progress_updated.emit(f"Pipeline Failed at Stage 1 (Exit Code: {exit_code})", 0)
            self.finished.emit(False)


class DashboardTab(QWidget):
    """Home Dashboard / System Monitor (CoChem-BASE)"""
    def __init__(self) -> None:
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
        self.start_btn.clicked.connect(self.start_pipeline)
        layout.addWidget(self.start_btn)

        layout.addStretch()

        # Timer for real HW metrics
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_hw_metrics)
        self.timer.start(1000)
        self.worker: Optional[PipelineWorker] = None

    def update_hw_metrics(self) -> None:
        """Query real system hardware metrics via psutil."""
        # Exception Deflection Test: Removed broad try/except swallowing. 
        # If psutil fails, it should raise and expose the OS dependency bug.
        cpu_val = int(psutil.cpu_percent())
        ram_val = int(psutil.virtual_memory().percent)

        gpu_val = 0
        if torch is not None and torch.cuda.is_available():
            if hasattr(torch.cuda, "utilization_rate"):
                gpu_val = int(torch.cuda.utilization_rate())

        self.cpu_bar.setValue(cpu_val)
        self.gpu_bar.setValue(gpu_val)
        self.ram_bar.setValue(ram_val)

    def start_pipeline(self) -> None:
        """Launches real pipeline execution via ExecutionRouter."""
        # Removed exception deflection around ExecutionRouter import/init.
        router = ExecutionRouter()

        self.start_btn.setEnabled(False)
        self.task_label.setText("Initializing Pipeline Router...")
        self.task_bar.setValue(0)

        self.worker = PipelineWorker(router)
        self.worker.progress_updated.connect(self._on_pipeline_progress)
        self.worker.finished.connect(self._on_pipeline_finished)
        self.worker.start()

    def _on_pipeline_progress(self, stage_name: str, percent: int) -> None:
        self.task_label.setText(f"Running: {stage_name}")
        self.task_bar.setValue(percent)

    def _on_pipeline_finished(self, success: bool) -> None:
        self.start_btn.setEnabled(True)
        if success:
            self.task_label.setText("Pipeline Execution Completed Successfully.")
            self.task_bar.setValue(100)
        else:
            self.task_label.setText("❌ Pipeline Execution Failed. Check Logs.")
