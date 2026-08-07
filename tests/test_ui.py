# tests/test_ui.py

from frontend.ui_components import format_inr, get_sample_questions


def test_format_inr():
    assert format_inr(25000000) == "₹2.50 Cr"
    assert format_inr(1500000) == "₹15.00 L"
    assert format_inr(45000) == "₹45,000"
    assert format_inr(0) == "₹0"
    assert format_inr(None) == "₹0"


def test_get_sample_questions():
    questions = get_sample_questions()
    assert isinstance(questions, list)
    assert len(questions) >= 5
    assert any("pipeline" in q.lower() for q in questions)
