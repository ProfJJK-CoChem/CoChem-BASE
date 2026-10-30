"""Real local help lookup and widget interactions, independent of engine access."""
from dataclasses import replace
from html.parser import HTMLParser
import os
from pathlib import Path
import subprocess
import sys

import ipywidgets as widgets
import pytest

from ci_tools.source_quarantine import source_paths
from ui.voila_layout.learning import (
    HELP_TOPICS, MAX_HELP_QUERY, build_learning_help, build_topic_answer, coverage_index,
    search_topics, topic_html,
)


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def _close_tree(widget):
    for child in getattr(widget, "children", ()):
        _close_tree(child)
    widget.close()


@pytest.fixture
def help_panel():
    help_panel = build_learning_help()
    yield help_panel
    _close_tree(help_panel.widget)


@pytest.mark.parametrize(("query", "expected"), [
    ("chiralty", "chirality"),
    ("Why are mirror images different?", "chirality"),
    ("What does R/S mean?", "chirality"),
    ("What is the difference between isomers and resonance?", "isomers"),
    ("What does a negative frequency mean?", "convergence_frequencies"),
    ("What total charge should I enter?", "charge_spin"),
    ("How do I start my first calculation?", "first_calculation"),
    ("Did my calculation succeed?", "read_results"),
])
def test_ordinary_questions_find_the_relevant_authored_explanation(query, expected):
    matches = search_topics(query)
    assert matches and expected in [topic.id for topic in matches[:3]]
    assert len(matches) <= 6
    assert all(topic.what and topic.how and topic.limitations for topic in matches)


def test_deliberate_alias_and_case_variants_rank_chirality_first():
    for query in ("chiralty", "CHIRALITY", "  chirality  "):
        assert search_topics(query)[0].id == "chirality"
    assert search_topics("chiralty") == search_topics("chiralty")


def test_search_is_bounded_and_shorter_query_can_recover():
    assert len(search_topics("energy", limit=2)) <= 2
    assert len(search_topics("energy", limit=12)) <= 12
    assert search_topics("chirality" + " " * MAX_HELP_QUERY + "irrelevantword") == search_topics("chirality")
    assert search_topics("qzxvvv_unmatchedzzzz") == ()
    assert search_topics("what is it and why") == ()
    assert search_topics("")[0].id == "first_calculation"
    assert search_topics("frequency")


@pytest.mark.parametrize("limit", [0, -1, 13, True, 2.5, "6"])
def test_unbounded_or_invalid_result_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        search_topics("energy", limit=limit)


def test_help_is_compact_and_uses_labelled_native_input_and_button(help_panel):
    assert isinstance(help_panel.widget, widgets.VBox)
    assert isinstance(help_panel.search, widgets.Text)
    assert help_panel.search.description == "Help search:"
    assert help_panel.clear.description == "Clear help"
    assert help_panel.clear.tooltip
    assert not help_panel.results.children
    status = Markup(help_panel.status.value)
    assert any(attrs.get("role") == "status" and attrs.get("aria-live") == "polite"
               for _, attrs in status.elements)
    assert "Offline help — no sign-in or calculation engine needed." in " ".join(status.text)


def test_live_widget_search_clear_and_context_open_use_the_same_content(help_panel):
    help_panel.search.value = "chiralty"
    assert help_panel.results.children
    assert search_topics("chiralty")[0].title in help_panel.results.children[0].value
    for child in help_panel.results.children:
        details = [attrs for tag, attrs in Markup(child.value).elements if tag == "details"]
        assert details and all("open" not in attrs for attrs in details)
    assert help_panel.open_topic("charge_spin") is True
    assert help_panel.search.value == ""
    assert len(help_panel.results.children) == 1
    markup = Markup(help_panel.results.children[0].value)
    details = [attrs for tag, attrs in markup.elements if tag == "details"]
    assert "open" in details[0] and "open" not in details[1]
    text = " ".join(markup.text)
    for label in ("What it means", "Why it matters", "When to use", "Where to find", "How to proceed", "Scientific limits"):
        assert label in text
    # The field is already empty: clearing must still close contextual help.
    help_panel.clear.click()
    assert help_panel.search.value == "" and not help_panel.results.children
    help_panel.search.value = "frequency"
    help_panel.clear.click()
    assert help_panel.search.value == "" and not help_panel.results.children


def test_repeated_search_does_not_allocate_an_output_model_per_keystroke(help_panel):
    identifiers = []
    for query in ("ch", "chir", "chiralty", "charge", "frequency", "energy", "chirality"):
        help_panel.search.value = query
        assert len(help_panel.results.children) == 1
        identifiers.append(help_panel.results.children[0].model_id)
    assert len(set(identifiers)) == 1


def test_empty_and_unknown_topic_states_are_explicit_escaped_and_recoverable(help_panel):
    query = '<script>qzxvvv_unmatchedzzzz</script>'
    help_panel.search.value = query
    assert not help_panel.results.children
    assert "No help topics match" in help_panel.status.value
    assert "&lt;script&gt;" in help_panel.status.value
    assert all(tag != "script" for tag, _ in Markup(help_panel.status.value).elements)
    assert help_panel.open_topic(query) is False
    assert "not available" in help_panel.status.value
    assert "&lt;script&gt;" in help_panel.status.value
    help_panel.search.value = "charge"
    assert help_panel.results.children
    assert "not available" not in help_panel.status.value


def test_authored_text_is_rendered_as_text_in_every_answer_field():
    original = search_topics("chirality")[0]
    unsafe = '<img src=x onerror="alert(1)"> & <script>bad()</script>'
    topic = replace(original, id=unsafe, title=unsafe, what=unsafe, why=unsafe, when=unsafe,
                    where=unsafe, how=(unsafe,), limitations=(unsafe,))
    markup = Markup(topic_html(topic, opened=True))
    assert not any(tag in {"img", "script"} for tag, _ in markup.elements)
    assert " ".join(markup.text).count(unsafe) == 7
    assert "&lt;img" in topic_html(topic)


def test_inline_and_search_answers_share_the_same_authored_content():
    answer = build_topic_answer("chirality")
    try:
        assert answer.value == topic_html(search_topics("chirality")[0], opened=True)
        assert 'data-help-topic="chirality"' in answer.value
        assert "cochem-context-answer" in answer._dom_classes
    finally:
        answer.close()
    with pytest.raises(KeyError):
        build_topic_answer("unknown_future_topic")


def test_coverage_inventory_reports_unmapped_controls_without_claiming_all_coverage():
    index = coverage_index()
    assert set(HELP_TOPICS) <= set(index["topic_ids"])
    assert not index["inventory_supplied"]
    assert index["control_topics"]
    known = next(iter(index["control_topics"]))
    observed = coverage_index((known, "unmapped_future_control"))
    assert observed["inventory_supplied"]
    assert observed["unmapped_controls"] == ("unmapped_future_control",)
    assert all(topic in index["topic_ids"] for topics in index["control_topics"].values() for topic in topics)
    assert "Other controls require an inventory review" in observed["scope"]


@pytest.mark.parametrize("control", ["charge_input", "matrix_method", "btn_actions_retrieve"])
def test_individual_control_instructions_are_searchable_and_visible(control):
    metadata = coverage_index()["control_metadata"][control]
    query = metadata.get("label") or metadata["hint"]
    matches = search_topics(query)
    assert metadata["topic"] in [topic.id for topic in matches[:3]]
    markup = Markup(topic_html(metadata["topic"], opened=True))
    assert any(attrs.get("data-help-control") == control for _, attrs in markup.elements)
    assert metadata["hint"] in " ".join(markup.text)
    assert metadata["location"] in " ".join(markup.text)


def test_real_help_runs_without_credentials_network_or_provider_processes(tmp_path):
    source = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(source)),
                       PYTHONDONTWRITEBYTECODE="1", PATH=str(tmp_path / "no-provider-binaries"))
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        environment.pop(key, None)
    child = r'''
import sys
from pathlib import Path
import os
source = Path(sys.argv[1]).resolve()
if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
    startup = sys.modules.get("sitecustomize")
    assert startup is not None
    assert Path(startup.__file__).resolve() == source / "ci_tools/quarantine_startup/sitecustomize.py"
    state = getattr(sys.modules.get("ci_tools.source_quarantine"), "_active", None)
    assert state is not None and state["copied"] == source
import ipywidgets
def refuse_external(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen"}:
        raise AssertionError("Offline help attempted external execution: " + event)
sys.addaudithook(refuse_external)
import ui.voila_layout.learning as learning
assert Path(learning.__file__).resolve() == source / "ui/voila_layout/learning.py"
panel = learning.build_learning_help()
panel.search.value = "chiralty"
assert panel.results.children and "hiral" in panel.results.children[0].value
assert panel.open_topic("first_calculation")
panel.clear.click()
assert panel.search.value == "" and not panel.results.children
assert not any(name.split(".")[0] in {"cochem_topos", "cochem_torq", "openai", "anthropic"} for name in sys.modules)
print("offline-help-widget-passed")
'''
    result = subprocess.run([sys.executable, "-B", "-c", child, str(source)], cwd=tmp_path,
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "offline-help-widget-passed" in result.stdout
