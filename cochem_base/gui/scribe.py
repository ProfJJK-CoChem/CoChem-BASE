import sys
from PySide6.QtWidgets import QDockWidget, QTextEdit, QWidget
from PySide6.QtCore import Qt, QObject, Signal
from typing import Optional, Any


class StreamSignals(QObject):
    text_written = Signal(str)


class OutputStream(QObject):
    """File-like object to intercept stdout/stderr and emit a signal"""
    def __init__(self, signals: StreamSignals) -> None:
        super().__init__()
        self.signals = signals

    def write(self, text: str) -> None:
        self.signals.text_written.emit(text)

    def flush(self) -> None:
        if hasattr(sys.__stdout__, "flush"):
            sys.__stdout__.flush()


class ScribeDock(QDockWidget):
    """Data Provenance & Asynchronous Logging Console (CoChem-SCRIBE)"""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("CoChem-SCRIBE (Data Provenance)", parent)
        self.setAllowedAreas(Qt.BottomDockWidgetArea)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.append("CoChem-Studio started. SCRIBE logging initialized.")
        self.setWidget(self.console)

        # Setup asynchronous stdout/stderr interception
        self.signals = StreamSignals()
        self.signals.text_written.connect(self.append_text)

        # Intercept
        sys.stdout = OutputStream(self.signals)
        sys.stderr = OutputStream(self.signals)

    def log(self, text: str) -> None:
        """Appends log message to console."""
        self.console.append(text)
        self.console.ensureCursorVisible()

    def append_text(self, text: str) -> None:
        self.console.insertPlainText(text)
        self.console.ensureCursorVisible()

    def closeEvent(self, event: Any) -> None:
        # Restore sys streams on close to avoid crash if sys.stdout is written to after dock destroyed
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        super().closeEvent(event)
