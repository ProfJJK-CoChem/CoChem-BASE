"""Lazy exports for optional browser interface components."""

from typing import Any

__all__ = ["WebSparsityMatrix", "WebGLStreamer"]


def __getattr__(name: str) -> Any:
    if name == "WebSparsityMatrix":
        from .web_matrices import WebSparsityMatrix
        return WebSparsityMatrix
    if name == "WebGLStreamer":
        from .web_streaming import WebGLStreamer
        return WebGLStreamer
    raise AttributeError(name)
