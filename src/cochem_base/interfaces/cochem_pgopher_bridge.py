"""PGOPHER downstream spectroscopy export contract.

This compatibility entrypoint prepares validated artifacts for integration.
It does not execute the former advertised solver or service API.
"""
from .integration_boundary import IntegrationBoundary

boundary = IntegrationBoundary(interface='cochem_pgopher_bridge', module_id='spycfit',
                               operation='pgopher_export', description='PGOPHER downstream spectroscopy export contract')
get_capability = boundary.capability
prepare_handoff = boundary.prepare_handoff
main = boundary.main

__all__ = ["boundary", "get_capability", "prepare_handoff", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
