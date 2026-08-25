import json
import pytest
from app.agent.memory import SessionMemory
from app.agent.orchestrator import AgentOrchestrator
from app.agent.llm_client import MockLLMClient

@pytest.fixture
def memory():
    return SessionMemory(max_history_turns=3)

@pytest.fixture
def agent():
    mock_llm = MockLLMClient()
    return AgentOrchestrator(llm_client=mock_llm)

def test_1_session_isolation(agent):
    res1 = agent.process_query("Where is ORD-1007?", session_id="session_A")
    assert res1.tool_used == "order_lookup"

    # Turn in session_B without order ID should not inherit session_A context
    res2 = agent.process_query("When will it arrive?", session_id="session_B")
    assert res2.trace_metadata["detected_order_id"] is None

def test_2_multi_turn_order_context_end_to_end(agent):
    """End-to-End Test: Turn 1 sets ORD-1007 context, Turn 2 resolves ORD-1007 from history."""
    session_id = "e2e_demo"
    res1 = agent.process_query("Where is ORD-1007?", session_id=session_id)
    assert res1.tool_used == "order_lookup"
    assert res1.trace_metadata["detected_order_id"] == "ORD-1007"

    # Turn 2 has no explicit order ID in prompt
    res2 = agent.process_query("When should it arrive?", session_id=session_id)
    assert res2.tool_used == "order_lookup"
    assert res2.trace_metadata["detected_order_id"] == "ORD-1007"
    assert res2.handoff is False

def test_3_ambiguous_multiple_order_context(agent):
    """Ambiguity Test: Referencing ORD-1007 then ORD-1010 makes implicit follow-up ambiguous."""
    session_id = "ambiguous_demo"
    agent.process_query("Where is ORD-1007?", session_id=session_id)
    agent.process_query("What about ORD-1010?", session_id=session_id)

    # Turn 3 is ambiguous
    res3 = agent.process_query("When will it arrive?", session_id=session_id)
    assert res3.handoff is True
    assert res3.handoff_reason == "ambiguous_order"
    assert "ORD-1007" in res3.answer
    assert "ORD-1010" in res3.answer

def test_4_memory_turn_limit(memory):
    session_id = "limit_test"
    for i in range(1, 10):
        memory.add_turn(session_id, f"Query {i}", f"Response {i}")

    history = memory.get_history(session_id)
    assert len(history) == 3
    assert history[0].user_message == "Query 7"
    assert history[-1].user_message == "Query 9"

def test_5_no_raw_order_records_in_memory(agent):
    session_id = "privacy_mem"
    agent.process_query("Where is ORD-1007?", session_id=session_id)
    history = agent.session_memory.get_history(session_id)

    assert len(history) == 1
    turn_str = json.dumps(history[0].model_dump())

    forbidden_terms = [
        "ava.morgan@example.test", "220 King Street", "risk_score", "warehouse_note", "support_tags", "82"
    ]
    for term in forbidden_terms:
        assert term not in turn_str, f"Forbidden PII/internal term '{term}' leaked into SessionMemory!"
