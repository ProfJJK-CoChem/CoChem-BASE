"""Remote artifact visualization contract.

This compatibility entrypoint prepares validated artifacts for integration.
It does not execute the former advertised solver or service API.
"""
from .integration_boundary import IntegrationBoundary

boundary = IntegrationBoundary(interface='cochem_dock_visuals_api', module_id='dock',
                               operation='visualize_artifact', description='Remote artifact visualization contract')
get_capability = boundary.capability
prepare_handoff = boundary.prepare_handoff
main = boundary.main

__all__ = ["boundary", "get_capability", "prepare_handoff", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
