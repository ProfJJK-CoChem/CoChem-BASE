"""Exercise the real offline help and glossary without inventing scientific results."""
from html.parser import HTMLParser

import ipywidgets as widgets
import pytest

from ui.voila_layout.learning import HELP_TOPICS, build_glossary, help_html, hint_html


class ParsedHelp(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


@pytest.mark.parametrize("topic", [
    "workspace", "scientific_inputs", "charge_spin", "method_basis", "theory_tiers",
    "solvent", "calculation_types", "convergence_frequencies", "fragments_constraints",
    "hessian", "active_space", "isotopes", "periodic", "compare_results", "provenance",
])
def test_contextual_help_has_a_closed_keyboard_native_disclosure_and_visible_hint(topic):
    assert topic in HELP_TOPICS
    parsed = ParsedHelp(help_html(topic))
    details = [attrs for tag, attrs in parsed.tags if tag == "details"]
    assert details == [{"class": "cochem-help"}]
    assert sum(tag == "summary" for tag, _ in parsed.tags) == 1
    assert parsed.text[0].startswith("Explain ")
    assert not any(tag in {"script", "iframe", "input"} for tag, _ in parsed.tags)
    hint = ParsedHelp(hint_html(topic))
    assert not any(tag == "details" for tag, _ in hint.tags)
    assert 8 <= len(" ".join(hint.text).split()) <= 40


def test_guidance_distinguishes_scientific_results_from_inputs_and_estimates():
    comparisons = " ".join(ParsedHelp(help_html("compare_results")).text).casefold()
    assert "electronic energy" in comparisons
    assert "free energy" in comparisons
    assert "standard state" in comparisons
    assert "equilibrium" in comparisons
    isotope = " ".join(ParsedHelp(help_html("isotopes")).text)
    assert "harmonic" in isotope and "anharmonic" in isotope
    tiers = " ".join(ParsedHelp(help_html("theory_tiers")).text)
    assert "not an accuracy guarantee" in tiers
    assert "not a promised runtime" in tiers
    charge = " ".join(ParsedHelp(help_html("charge_spin")).text)
    assert "2S + 1" in charge and "doublet" in charge


def test_input_guidance_covers_ensembles_native_outputs_and_periodic_data():
    text = " ".join(ParsedHelp(help_html("scientific_inputs")).text)
    for required in ("SDF", "MOL2", "PDB", "CIF", "HDF5", "NPZ", "Hessian", "CREST", "GOAT"):
        assert required in text
    for required in ("original", "frame", "isotope", "SMILES"):
        assert required.casefold() in text.casefold()


@pytest.fixture
def glossary():
    panel = build_glossary()
    yield panel
    for child in panel.children:
        child.close()
    panel.close()


def test_glossary_filters_real_terms_case_insensitively_and_can_be_cleared(glossary):
    heading, search, results = glossary.children
    assert "Scientific terms" in heading.value
    assert isinstance(search, widgets.Text)
    assert search.description and search.placeholder
    original = results.value
    assert 25 <= original.count("<summary>") <= 35
    search.value = "   cOuNtErPoIsE   "
    assert "Counterpoise" in results.value
    assert results.value.count("<summary>") == 1
    assert "<summary>Hessian</summary>" not in results.value
    assert search.value == "   cOuNtErPoIsE   "
    search.value = ""
    assert results.value == original


def test_glossary_can_find_chemistry_abbreviations_and_explanations(glossary):
    search, results = glossary.children[1:]
    search.value = "SCF"
    assert "Self-consistent field" in results.value
    search.value = "2S + 1"
    assert "Spin multiplicity" in results.value
    search.value = "zero-point"
    assert "Zero-point energy" in results.value


def test_glossary_escapes_search_text_and_explains_empty_results(glossary):
    search, results = glossary.children[1:]
    search.value = '<img src=x onerror="alert(1)">'
    assert "No terms match" in results.value
    assert "&lt;img" in results.value
    assert "Try a shorter word" in results.value
    assert not any(tag in {"img", "script"} for tag, _ in ParsedHelp(results.value).tags)
    search.value = "isotope"
    assert "Isotope" in results.value
    assert "&lt;img" not in results.value


def test_unknown_help_topic_fails_instead_of_silently_displaying_unrelated_guidance():
    with pytest.raises(KeyError):
        help_html("not-a-supported-topic")
    with pytest.raises(KeyError):
        hint_html("not-a-supported-topic")


@pytest.mark.parametrize(("code", "meaning"), [
    ("prepared", "request prepared"),
    ("submitted", "submission recorded"),
    ("cancellation_requested", "waiting for GitHub"),
    ("awaiting_workflow", "waiting for GitHub"),
    ("dispatch_unconfirmed", "confirm submission"),
    ("dispatching", "request received; waiting for the run"),
    ("queued", "queued; waiting to run"),
    ("in_progress", "running"),
    ("updates_available", "updates are available"),
    ("rolled_back", "previous version restored"),
])
def test_progress_labels_explain_protocol_states_without_changing_them(code, meaning):
    from ui.voila_layout.learning import progress_label

    assert meaning in progress_label(code)
    assert "_" not in progress_label(code)


def test_unknown_progress_is_not_presented_as_success():
    from ui.voila_layout.learning import progress_label

    label = progress_label("unrecognized_future_state")
    assert "check details" in label
    assert "success" not in label and "completed" not in label
