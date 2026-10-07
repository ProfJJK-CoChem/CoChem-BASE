"""Compatibility cleanup restricted to explicitly registered CoChem processes."""


def reap_owned_children() -> None:
    """Poll only handles registered by CoChem's subprocess broker.

    A direct child can belong to another library, including multiprocessing's
    resource tracker. Its owner must retain the right to collect its exit status.
    The broker already registers its own shutdown hook and manages live children;
    setup imports must not install additional process-tree or host-wide sweepers.
    """
    from cochem_base.core_engine.cochem_core_subprocess_broker import get_active_popen_processes

    # The broker polls its registered Popen handles while pruning exited entries.
    # Popen retains each exit status for the handle's original caller.
    get_active_popen_processes()
