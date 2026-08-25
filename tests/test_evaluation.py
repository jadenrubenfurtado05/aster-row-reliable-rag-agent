import json
from pathlib import Path
import pytest
from app.schemas import AgentResponse
from evaluation.evaluators import CaseEvaluator
from evaluation.run_eval import run_evaluation

def test_1_eval_file_loads_correctly():
    eval_path = Path("evaluation/visible-cases.json")
    assert eval_path.exists()
    with open(eval_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "cases" in data
    assert len(data["cases"]) == 15

def test_2_3_4_evaluation_harness_processing():
    summary = run_evaluation()
    assert "total" in summary
    assert "passed" in summary
    assert "failed" in summary
    assert "pass_rate" in summary
    assert summary["total"] == 15

def test_5_source_validation():
    response = AgentResponse(
        answer="The return window is 30 days.",
        sources=["01-returns-policy-current.md#Standard return window"]
    )
    expect_spec = {
        "required_sources": ["01-returns-policy-current.md"],
        "forbidden_sources_as_authority": ["02-returns-policy-legacy.md"]
    }
    passed, failures = CaseEvaluator.evaluate_case(response, expect_spec)
    assert passed is True

    # Test failure when required source is missing
    bad_spec = {"required_sources": ["09-trailplus-membership.md"]}
    passed_bad, failures_bad = CaseEvaluator.evaluate_case(response, bad_spec)
    assert passed_bad is False

def test_6_handoff_validation():
    response = AgentResponse(
        answer="Please contact human support.",
        handoff=True
    )
    expect_spec = {"handoff": True}
    passed, _ = CaseEvaluator.evaluate_case(response, expect_spec)
    assert passed is True

    bad_spec = {"handoff": False}
    passed_bad, failures_bad = CaseEvaluator.evaluate_case(response, bad_spec)
    assert passed_bad is False

def test_7_flexible_natural_language_answer_checking():
    response = AgentResponse(
        answer="Standard plan customers have thirty calendar days from delivery date to request a return.",
        sources=["01-returns-policy-current.md#Standard return window"]
    )
    expect_spec = {
        "must_include": ["delivery"],
        "must_not_include": ["60 days"]
    }
    passed, failures = CaseEvaluator.evaluate_case(response, expect_spec)
    assert passed is True

def test_8_raw_customer_data_not_exposed():
    summary = run_evaluation()
    summary_str = json.dumps(summary)
    forbidden_terms = [
        "ava.morgan@example.test", "220 King Street", "risk_score", "warehouse_note", "support_tags"
    ]
    for term in forbidden_terms:
        assert term not in summary_str, f"Forbidden customer PII '{term}' leaked in evaluation summary!"

def test_9_evaluator_handles_malformed_case_safely():
    malformed_response = AgentResponse(answer="")
    malformed_spec = {"must_include": ["non_existent_substring_xyz"]}
    passed, failures = CaseEvaluator.evaluate_case(malformed_response, malformed_spec)
    assert passed is False
    assert len(failures) > 0

def test_10_evaluator_does_not_modify_supplied_data():
    eval_path = Path("evaluation/visible-cases.json")
    original_bytes = eval_path.read_bytes()
    run_evaluation()
    current_bytes = eval_path.read_bytes()
    assert original_bytes == current_bytes
