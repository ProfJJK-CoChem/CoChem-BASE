# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
WebGL and UI Rendering Performance Monitor for CoChem-BENCH.
Strictly adheres to Anti-Spoofing Directives: never simulates rendering bottlenecks with synthetic CPU math loops.
"""

import collections
import logging
import time

logger = logging.getLogger(__name__)

class WebGLPerformanceTracker:
    """
    Tracks WebGL rendering pipeline latency and determines if fallback
    to SVG/Canvas is required based on empirical hardware frame metrics.
    """
    def __init__(self, fps_threshold: float = 30.0):
        if fps_threshold <= 0:
            raise ValueError("fps_threshold must be greater than 0")
        self.fps_threshold = fps_threshold
        self.current_fps: float = 0.0
        self.is_svg_fallback_active: bool = False
        self._frame_times: collections.deque[float] = collections.deque(maxlen=120)

    def record_frame(self, frame_duration_seconds: float) -> None:
        """Records an actual empirical frame duration from the rendering viewport."""
        if frame_duration_seconds <= 0:
            return
        self._frame_times.append(frame_duration_seconds)
            
        avg_time = sum(self._frame_times) / len(self._frame_times)
        self.current_fps = 1.0 / avg_time if avg_time > 0 else 0.0
        self.is_svg_fallback_active = (self.current_fps < self.fps_threshold)

    def evaluate_performance(self, measured_fps: float | None = None) -> tuple[bool, float]:
        """
        Evaluates rendering performance using measured hardware FPS.
        If no hardware metrics are available (e.g. headless CI), reports 0.0 and triggers SVG fallback safely.
        """
        if measured_fps is not None:
            if measured_fps < 0:
                raise ValueError("measured_fps must be non-negative")
            self.current_fps = measured_fps
            self.is_svg_fallback_active = (self.current_fps < self.fps_threshold)
        elif not self._frame_times:
            # Headless or unmeasured environment
            logger.info("No active display context detected; defaulting to SVG rendering mode.")
            self.current_fps = 0.0
            self.is_svg_fallback_active = True
            
        return self.is_svg_fallback_active, self.current_fps

    def get_rendering_mode(self) -> str:
        """Returns the active rendering mode based on empirical performance."""
        return "SVG" if self.is_svg_fallback_active else "WebGL"
