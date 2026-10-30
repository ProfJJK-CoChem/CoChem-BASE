"""Exercise startup acknowledgement through an actual isolated kernel's comms.

These are widget-protocol engineering controls, not native chemistry or browser
view-creation acceptance. Actual display acknowledgements are qualified by the
canonical Start_Here browser lane separately.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import ipywidgets as widgets
from jupyter_client import KernelManager
import pytest
from traitlets import Int

from ci_tools.source_quarantine import source_paths
from ui.voila_layout.initial_widget_state import (
    UnsupportedWidgetRuntime, _supported_version, arm_initial_widget_state,
)


def _messages(client, parent):
    messages = []
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        message = client.get_iopub_msg(timeout=max(.1, deadline - time.monotonic()))
        if message.get("parent_header", {}).get("msg_id") != parent:
            continue
        messages.append(message)
        if (message["msg_type"] == "status"
                and message["content"].get("execution_state") == "idle"):
            return messages
    raise AssertionError("The owned kernel did not complete the comm request")


def _execute(client, code):
    request = client.execute(code, store_history=False)
    messages = _messages(client, request)
    errors = [m["content"] for m in messages if m["msg_type"] == "error"]
    assert not errors, errors
    return messages


def _observe(client, expression):
    messages = _execute(client, "print(__import__('json').dumps(" + expression + "))")
    text = "".join(m["content"]["text"] for m in messages if m["msg_type"] == "stream")
    return json.loads(text)


def _comm(client, model_id, state):
    message = client.session.send(client.shell_channel.socket, "comm_msg", content={
        "comm_id": model_id, "data": {"method": "update", "state": state, "buffer_paths": []}})
    return message["header"]["msg_id"]


def _updates(messages, model_id):
    return [m["content"]["data"]["state"] for m in messages if m["msg_type"] == "comm_msg"
        and m["content"].get("comm_id") == model_id
        and m["content"].get("data", {}).get("method") == "update"]


@pytest.fixture
def kernel(tmp_path):
    source = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(source)),
        PYTHONDONTWRITEBYTECODE="1", IPYTHONDIR=str(tmp_path / "ipython"),
        COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"), COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
        COCHEM_STUDENT_AUTO_SETUP="0", COCHEM_STUDENT_AUTO_REMOTE_CHECK="0")
    manager = KernelManager(connection_file=str(tmp_path / "owned-kernel.json"))
    manager.kernel_spec.argv = [sys.executable, "-B", "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    manager.start_kernel(cwd=str(source), env=environment)
    client = manager.client()
    client.start_channels()
    try:
        client.wait_for_ready(timeout=30)
        _execute(client, """
from pathlib import Path
import os, sys
import ipywidgets as widgets
import ui.voila_layout.initial_widget_state as startup_sync
from ui.voila_layout.initial_widget_state import arm_initial_widget_state
""" + f"assert Path(startup_sync.__file__).resolve() == Path({str(source / 'ui/voila_layout/initial_widget_state.py')!r})\n" + """
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    boundary = sys.modules.get('ci_tools.source_quarantine')
    assert boundary is not None and boundary._active is not None
    assert boundary._active['copied'] == Path(os.environ['COCHEM_SOURCE_QUARANTINE_ROOT'])
""")
        yield client
    finally:
        client.stop_channels()
        manager.shutdown_kernel(now=True)
        manager.cleanup_resources()


def test_actual_gui_target_scope_and_real_widget_comm_replay_once(kernel):
    client = kernel
    _execute(client, """
from ui.voila_layout.cochem_gui import CoChemGUI
gui = CoChemGUI()
models = gui._initial_library_state_models
assert len(models) == 15 and len({m.model_id for m in models}) == 15
assert all(m._view_count == 0 for m in models)
assert models[:3] == (gui.input_library_table, gui.input_library_rejections, gui.input_library_status)
assert models[3:6] == (gui.btn_input_refresh, gui.btn_use_input_geometry, gui.btn_remove_input)
assert models[6:9] == (gui.input_library_choice, gui.input_record_choice, gui.input_pool_choices)
assert models[9:] == tuple(gui._input_selectors.values())
assert gui.input_library_choice.index == 0 and gui.input_record_choice.index is None
assert gui.input_pool_choices.index == ()
assert all(m.index == 0 for m in gui._input_selectors.values())
draft = (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
         gui.matrix_engine.value, gui.matrix_method.value, gui.matrix_basis.value, gui.product_class_selector.value)
assert gui.student_geometry_choice not in models and gui.matrix_geometry not in models
protocol_models = [widgets.HTML() for _ in range(3)] + [widgets.Button(disabled=False) for _ in range(3)]
protocol_models += [widgets.Dropdown(options=[('Choose input','')]) for _ in range(2)]
protocol_models += [widgets.SelectMultiple(options=[])]
protocol_models += [widgets.Dropdown(options=[('Choose input','')]) for _ in range(6)]
for number, model in enumerate(protocol_models):
    arm_initial_widget_state(model)
    if isinstance(model, widgets.HTML):
        model.value = '<p>Actual engineering display state ' + str(number) + '</p>'
    elif isinstance(model, widgets.Button):
        model.disabled = True
    else:
        model.options = [('Choose input',''),('Retained input','retained')]
expected_fields = [{key:model.get_state(key=key)[key] for key in
    (('value',) if isinstance(model,widgets.HTML) else ('disabled',) if isinstance(model,widgets.Button) else ('_options_labels',))}
    for model in protocol_models]
""")
    observed = _observe(client, "{'ids':[m.model_id for m in protocol_models], 'fields':expected_fields}")
    for number, model_id in enumerate(observed["ids"]):
        messages = _messages(client, _comm(client, model_id, {"_view_count": 1}))
        assert _updates(messages, model_id) == [observed["fields"][number]]
        if number >= 6:
            assert not ({"index", "value"} & set(observed["fields"][number]))
        assert not _updates(_messages(client, _comm(client, model_id, {"_view_count": 2})), model_id)
        assert not _updates(_messages(client, _comm(client, model_id, {"_view_count": 0})), model_id)
        assert not _updates(_messages(client, _comm(client, model_id, {"_view_count": 1})), model_id)
    _execute(client, """
assert draft == (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
    gui.matrix_engine.value, gui.matrix_method.value, gui.matrix_basis.value, gui.product_class_selector.value)
""")


def test_queued_and_combined_user_selections_are_not_replayed(kernel):
    client = kernel
    _execute(client, """
choices = [widgets.Dropdown(options=[('Choose input',''),('First','first'),('Second','second')]) for _ in range(2)]
for model in choices:
    arm_initial_widget_state(model)
    model.value = 'first'
""")
    ids = _observe(client, "[m.model_id for m in choices]")
    ack = _comm(client, ids[0], {"_view_count": 1})
    pending_selection = _comm(client, ids[0], {"index": 2})
    updates = _updates(_messages(client, ack), ids[0])
    _messages(client, pending_selection)
    assert updates == [{"_options_labels": ["Choose input", "First", "Second"]}]
    combined = _updates(_messages(client, _comm(client, ids[1], {"_view_count": 1, "index": 2})), ids[1])
    assert combined == [{"_options_labels": ["Choose input", "First", "Second"]}]
    assert _observe(client, "[m.value for m in choices]") == ["second", "second"]


def test_label_growth_and_reordering_never_replay_or_change_indices(kernel):
    client = kernel
    _execute(client, """
catalogs = [widgets.Dropdown(options=[('Choose input',''),('First','first'),('Second','second')]) for _ in range(2)]
for model in catalogs:
    arm_initial_widget_state(model)
catalogs[0].options = [('Choose input',''),('First','first'),('Second','second'),('Third','third')]
catalogs[1].options = [('Choose input',''),('Second','second'),('First','first')]
for model in catalogs:
    model.value = 'second'
""")
    before = _observe(client, "[{'id':m.model_id,'labels':list(m._options_labels),'index':m.index,'value':m.value} for m in catalogs]")
    for item in before:
        updates = _updates(_messages(client, _comm(client, item["id"], {"_view_count": 1})), item["id"])
        assert updates == [{"_options_labels": item["labels"]}]
    after = _observe(client, "[{'id':m.model_id,'labels':list(m._options_labels),'index':m.index,'value':m.value} for m in catalogs]")
    assert after == before  # No claim of repairing a stale frontend index/identity.


def test_runtime_features_and_editable_controls_fail_explicitly():
    class UnsynchronizedDisplay(widgets.HTML):
        _view_count = Int(None, allow_none=True)

    unsupported = UnsynchronizedDisplay(value="Existing display")
    with pytest.raises(UnsupportedWidgetRuntime, match="synchronized startup display acknowledgement"):
        arm_initial_widget_state(unsupported)
    editable = widgets.Text(value="Student draft")
    with pytest.raises(ValueError, match="library selectors only"):
        arm_initial_widget_state(editable)
    assert editable.value == "Student draft" and editable._view_count is None
    assert not _supported_version("8.0.9") and not _supported_version("9.0.0")
    assert not _supported_version("9.0rc1") and not _supported_version("9.0.dev1")
    assert not _supported_version("unidentified")
    assert _supported_version("8.1.0") and _supported_version("8.1.9")
