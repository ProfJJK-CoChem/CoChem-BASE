"""Legacy DOCK entrypoint migrated to the BASE artifact integration contract.

Use the native BASE calculation service for local jobs. Remote DOCK service
execution requires its separately installed and validated module adapter.
"""
from .cochem_dock_main import boundary, get_capability, main, prepare_handoff

__all__ = ["boundary", "get_capability", "prepare_handoff", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
