"""Student restart and two-tab recovery use the real per-project record on disk."""
import json
from types import SimpleNamespace

import ipywidgets as widgets

from ui.voila_layout.student_conformer_panel import StudentConformerPanel


def test_pending_dispatch_survives_reopening_and_requires_an_explicit_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("COCHEM_ARTIFACTS", str(tmp_path))
    repository = "course/student-work"
    def panel():
        return StudentConformerPanel(SimpleNamespace(gh_repo_input=widgets.Text(value=repository)))

    first = panel()
    path = first._record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = {"repository": repository, "pending": "interrupted-request"}
    path.write_text(json.dumps(pending), encoding="utf-8")

    # The first tab still displays the earlier editable state. A second click
    # must discover the durable record before any dispatch is attempted.
    first.run.click()
    assert first.run.disabled and first.record == pending
    reopened = panel()
    assert reopened.run.disabled and not reopened.address.value
    assert "no confirmed run link" in reopened.status.value
    reopened.repo.value = "course/other-work"
    assert not reopened.run.disabled
    reopened.repo.value = repository
    assert reopened.run.disabled
    reopened.reset.click()
    assert not reopened.run.disabled and not path.exists()

