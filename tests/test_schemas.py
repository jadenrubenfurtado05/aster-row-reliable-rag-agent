import pytest
from pydantic import ValidationError
from app.schemas import RetrievedChunk, SanitizedOrderResult, AgentResponse

def test_retrieved_chunk_valid():
    chunk = RetrievedChunk(
        source_filename="01-returns-policy-current.md",
        document_id="RET-2026-01",
        heading="Standard return window",
        text="Customers on the standard plan may request a return within 30 calendar days.",
        similarity_score=0.89,
        status="active",
        policy_authority="official",
        audience="customer",
        effective_date="2026-04-01"
    )
    assert chunk.source_filename == "01-returns-policy-current.md"
    assert chunk.similarity_score == 0.89
    assert chunk.status == "active"

def test_retrieved_chunk_invalid():
    with pytest.raises(ValidationError):
        # Missing required fields like similarity_score, heading, text
        RetrievedChunk(
            source_filename="01-returns-policy-current.md",
            status="active"
        )

def test_sanitized_order_result_valid():
    order = SanitizedOrderResult(
        order_id="ORD-1007",
        status="shipped",
        carrier="UPS",
        tracking_number="1ZAR100700000007",
        estimated_delivery="2026-08-22",
        customer_safe_message="The order is in transit with UPS."
    )
    assert order.order_id == "ORD-1007"
    assert order.status == "shipped"
    assert order.handoff_required is False

def test_sanitized_order_result_invalid():
    with pytest.raises(ValidationError):
        # Missing required order_id and status
        SanitizedOrderResult(carrier="UPS")

def test_agent_response_valid():
    resp = AgentResponse(
        answer="The return window is 30 calendar days from delivery.",
        sources=["01-returns-policy-current.md#Standard return window"],
        handoff=False
    )
    assert resp.answer.startswith("The return window")
    assert len(resp.sources) == 1
    assert resp.handoff is False
