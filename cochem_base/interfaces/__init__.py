"""Lazy exports for optional browser interface components."""

from typing import Any

__all__ = ["WebSparsityMatrix", "WebGLStreamer", "WebGLPacket"]


def __getattr__(name: str) -> Any:
    if name == "WebSparsityMatrix":
        from .web_matrices import WebSparsityMatrix
        return WebSparsityMatrix
    if name == "WebGLStreamer":
        from .web_streaming import WebGLStreamer
        return WebGLStreamer
    if name == "WebGLPacket":
        from .web_streaming import WebGLPacket
        return WebGLPacket
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return __all__
