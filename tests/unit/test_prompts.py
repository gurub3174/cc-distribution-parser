"""Tests for prompt modules — contract surface only.

Content tuning happens in a separate workflow with real docs.
"""

from __future__ import annotations

from cc_distribution_parser.prompts import classifier, extract_cc, extract_distro


def test_classifier_exports_required_surface():
    assert classifier.version.startswith("classifier@")
    assert isinstance(classifier.SYSTEM_PROMPT, str)
    assert isinstance(classifier.USER_TEMPLATE, str)
    h1 = classifier.compute_hash("abc")
    h2 = classifier.compute_hash("abc")
    h3 = classifier.compute_hash("def")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_extract_cc_exports_required_surface():
    assert extract_cc.version.startswith("extract_cc@")
    assert "unfunded" in extract_cc.SYSTEM_PROMPT.lower()
    assert "{wrapped_document}" in extract_cc.USER_TEMPLATE


def test_extract_distro_exports_required_surface():
    assert extract_distro.version.startswith("extract_distro@")
    assert "distribution_type" in extract_distro.SYSTEM_PROMPT
    assert "{wrapped_document}" in extract_distro.USER_TEMPLATE
