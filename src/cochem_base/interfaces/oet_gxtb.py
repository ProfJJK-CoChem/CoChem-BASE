"""Unconnected g-xTB ExtOpt integration contract.

This compatibility entrypoint prepares validated artifacts for integration.
It does not execute the former advertised solver or service API.
"""
from .integration_boundary import IntegrationBoundary

boundary = IntegrationBoundary(interface='oet_gxtb', module_id='base',
                               operation='extopt_gxtb', description='Unconnected g-xTB ExtOpt integration contract')
get_capability = boundary.capability
prepare_handoff = boundary.prepare_handoff
main = boundary.main

__all__ = ["boundary", "get_capability", "prepare_handoff", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
