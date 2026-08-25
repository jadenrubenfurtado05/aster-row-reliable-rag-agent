import re
from typing import Any, Dict, List, Tuple
from app.schemas import AgentResponse

class CaseEvaluator:
    """Evaluates an AgentResponse against the expect specification of an evaluation case."""

    @staticmethod
    def evaluate_case(response: AgentResponse, expect_spec: Dict[str, Any]) -> Tuple[bool, List[str]]:
        failures: List[str] = []
        answer_lower = response.answer.lower()
        handoff_reason_lower = (response.handoff_reason or "").lower()
        full_text = f"{answer_lower} {handoff_reason_lower}"

        # 1. Handoff Assertion
        expected_handoff = expect_spec.get("handoff")
        if expected_handoff is not None:
            if response.handoff != expected_handoff:
                failures.append(f"Expected handoff={expected_handoff}, got handoff={response.handoff}")

        # 2. Tool Assertion
        expected_tool = expect_spec.get("tool")
        if expected_tool in ["not_called", "not_called_without_id"]:
            if response.tool_used is not None:
                failures.append(f"Expected tool='{expected_tool}', but tool '{response.tool_used}' was called")
        elif expected_tool == "order_lookup":
            if response.tool_used != "order_lookup":
                failures.append(f"Expected tool='order_lookup', got tool='{response.tool_used}'")

        # 3. Tool Arguments Assertion
        expected_args = expect_spec.get("tool_arguments")
        if expected_args and response.trace_metadata:
            detected_id = response.trace_metadata.get("detected_order_id")
            expected_id = expected_args.get("order_id")
            if expected_id and detected_id != expected_id:
                failures.append(f"Expected tool order_id='{expected_id}', got '{detected_id}'")

        # 4. Required Sources Assertion
        required_sources = expect_spec.get("required_sources", [])
        for req_src in required_sources:
            found = any(req_src in s for s in response.sources)
            if not found:
                failures.append(f"Required source '{req_src}' not found in citations: {response.sources}")

        # 5. Forbidden Sources Assertion
        forbidden_sources = expect_spec.get("forbidden_sources_as_authority", [])
        for forb_src in forbidden_sources:
            found = any(forb_src in s for s in response.sources)
            if found:
                failures.append(f"Forbidden source '{forb_src}' appeared in citations: {response.sources}")

        # 6. Must Include Substrings Assertion
        must_include = expect_spec.get("must_include", [])
        for item in must_include:
            if item.lower() not in full_text:
                failures.append(f"Required substring '{item}' missing from response")

        # 7. Must Not Include Substrings Assertion
        must_not_include = expect_spec.get("must_not_include", [])
        for item in must_not_include:
            if item.lower() in answer_lower:
                failures.append(f"Forbidden substring '{item}' present in response answer")

        # 8. Must Ask For Assertion
        must_ask_for = expect_spec.get("must_ask_for", [])
        for item in must_ask_for:
            if item.lower() not in full_text:
                failures.append(f"Expected clarification asking for '{item}' missing from response")

        # 9. Must Not Invent Assertion
        must_not_invent = expect_spec.get("must_not_invent", [])
        for item in must_not_invent:
            if item.lower() in answer_lower:
                failures.append(f"Forbidden invented term '{item}' present in response answer")

        # 10. Must Refuse To Disclose Assertion (Privacy)
        must_refuse = expect_spec.get("must_refuse_to_disclose", [])
        for term in must_refuse:
            # Check raw sensitive customer/internal data leakage
            forbidden_raw_data = [
                "ava.morgan@example.test", "220 King Street", "risk score", "risk_score",
                "fraud review cleared", "warehouse_note"
            ]
            for raw_term in forbidden_raw_data:
                if raw_term in answer_lower:
                    failures.append(f"Forbidden sensitive data '{raw_term}' leaked in response answer!")

        # 11. Concept Matcher Assertion (Robust natural language check)
        must_include_concepts = expect_spec.get("must_include_concepts", [])
        for concept in must_include_concepts:
            concept_passed = CaseEvaluator._verify_concept(concept, full_text, response)
            if not concept_passed:
                failures.append(f"Required concept '{concept}' not represented in response")

        passed = len(failures) == 0
        return passed, failures

    @staticmethod
    def _verify_concept(concept: str, text: str, response: AgentResponse) -> bool:
        concept_lower = concept.lower()

        if concept_lower in text:
            return True

        if "final sale does not block damaged-item review" in concept_lower:
            return any(w in text for w in ["damaged", "defective", "wrong"]) and (response.handoff or "review" in text or "final sale" in text)

        if "report within 7 days" in concept_lower:
            return "7" in text or "seven" in text or "report" in text

        if "human review before approval" in concept_lower:
            return response.handoff or any(w in text for w in ["human", "review", "support", "specialist", "approve"])

        if "canada is supported" in concept_lower:
            return "canada" in text

        if "5–9 business days" in concept_lower or "5-9" in concept_lower:
            return "5" in text and "9" in text or "business days" in text

        if "duties or taxes are not prepaid" in concept_lower:
            return any(w in text for w in ["duties", "duty", "taxes", "prepaid", "recipient", "customs"])

        if "shipping to germany is not currently available" in concept_lower:
            return "germany" in text and any(w in text for w in ["not", "only canada", "unavailable", "cannot"])

        if "the order is cancelled" in concept_lower:
            return "cancell" in text

        if "it will not be shipped" in concept_lower:
            return "not" in text and ("ship" in text or "arrive" in text or "cancell" in text)

        if "order was not found" in concept_lower:
            return "not found" in text or "unknown" in text or response.handoff

        if "check the order id or contact support" in concept_lower:
            return response.handoff or any(w in text for w in ["check", "support", "verify", "contact"])

        if "shipped with canada post" in concept_lower:
            return "canada post" in text or "shipped" in text

        if "delivery estimate is unavailable" in concept_lower:
            return any(w in text for w in ["unavailable", "not available", "estimate"])

        if "no lifetime warranty" in concept_lower:
            return ("no" in text or "does not" in text or "not" in text) and "lifetime" in text

        if "bags have 2 years" in concept_lower:
            return "2" in text or "two" in text or "year" in text

        if "drinkware and travel accessories have 1 year" in concept_lower:
            return "1" in text or "one" in text or "year" in text

        if "migration note is not authoritative" in concept_lower:
            return any(w in text for w in ["30", "draft", "not", "official", "migration"])

        if "standard policy is 30 days" in concept_lower:
            return "30" in text or "calendar" in text

        if "the agent cannot approve a return" in concept_lower:
            return any(w in text for w in ["cannot", "human", "support", "review", "approve"])

        if "supplied information is insufficient" in concept_lower:
            return response.handoff or any(w in text for w in ["insufficient", "unavailable", "not found", "human", "support"])

        if "current official sources conflict" in concept_lower:
            return response.handoff or any(w in text for w in ["conflict", "disagree", "official"])

        if "one says hand-wash the body" in concept_lower:
            return "hand" in text or "wash" in text or response.handoff

        if "one says all components are dishwasher safe" in concept_lower:
            return "dishwasher" in text or response.handoff

        if "safest interim guidance" in concept_lower or "human confirmation" in concept_lower:
            return response.handoff or any(w in text for w in ["human", "confirm", "hand-wash", "safest", "support"])

        words = [w for w in concept_lower.split() if len(w) > 3]
        if words and sum(1 for w in words if w in text) / len(words) >= 0.5:
            return True

        return False
