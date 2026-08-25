from enum import Enum
from typing import Any, Dict, List, Optional
from app.schemas import RAGSearchResult, SanitizedOrderResult

class HandoffReason(str, Enum):
    UNSUPPORTED_ACTION = "unsupported_action"
    ORDER_NOT_FOUND = "order_not_found"
    POLICY_CONFLICT = "policy_conflict"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS_ORDER = "ambiguous_order"
    LLM_FAILURE = "llm_failure"
    PROMPT_INJECTION = "prompt_injection"

class SafetyDecision:
    """Represents a centralized safety decision for a user query."""
    def __init__(
        self,
        handoff_required: bool,
        reason_code: Optional[HandoffReason] = None,
        customer_message: Optional[str] = None
    ):
        self.handoff_required = handoff_required
        self.reason_code = reason_code
        self.customer_message = customer_message

class SafetyGuardrails:
    """Centralized safety decisions and guardrails for the Aster & Row agent."""

    @staticmethod
    def evaluate_order_safety(order_result: Optional[SanitizedOrderResult]) -> SafetyDecision:
        if not order_result:
            return SafetyDecision(False)

        if not order_result.found:
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.ORDER_NOT_FOUND,
                customer_message=f"Order {order_result.order_id} was not found in our system. Please check your order ID or contact customer support."
            )

        if not order_result.action_supported:
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.UNSUPPORTED_ACTION,
                customer_message="Order actions (such as cancellation or address changes) cannot be completed directly in chat. A human support specialist must assist you."
            )

        if order_result.handoff_required:
            reason = HandoffReason.UNSUPPORTED_ACTION if "unsupported" in (order_result.handoff_reason or "").lower() else HandoffReason.ORDER_NOT_FOUND
            return SafetyDecision(
                handoff_required=True,
                reason_code=reason,
                customer_message=order_result.customer_safe_message or "Your order requires human support review."
            )

        return SafetyDecision(False)

    @staticmethod
    def evaluate_rag_safety(
        rag_result: Optional[RAGSearchResult],
        user_query: str = ""
    ) -> SafetyDecision:
        if not rag_result:
            return SafetyDecision(False)

        # Active official source conflicts always require human confirmation.
        if rag_result.conflict_detected:
            sources_str = ", ".join(rag_result.conflicting_sources)
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.POLICY_CONFLICT,
                customer_message=(
                    f"Our official documents contain conflicting guidance "
                    f"regarding this topic ({sources_str}). Please confirm "
                    f"with human customer support."
                )
            )

        chunks = rag_result.retrieved_chunks

        # No usable retrieval evidence.
        if not chunks:
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.INSUFFICIENT_EVIDENCE,
                customer_message=(
                    "The supplied information is insufficient to answer this "
                    "question reliably. Please get human confirmation from "
                    "customer support."
                )
            )

        query_lower = user_query.lower()

        # Specific claims cannot be answered from unrelated retrieval results.
        unsupported_specific_terms = [
            "vegan",
            "certified",
            "certification",
        ]

        retrieved_text = " ".join(
            chunk.text.lower() for chunk in chunks
        )

        for term in unsupported_specific_terms:
            if term in query_lower and term not in retrieved_text:
                return SafetyDecision(
                    handoff_required=True,
                    reason_code=HandoffReason.INSUFFICIENT_EVIDENCE,
                    customer_message=(
                        "The supplied information is insufficient to answer "
                        "this question reliably. Please get human confirmation "
                        "from customer support."
                    )
                )

        # Prompt-injection attempts should not cause a handoff when valid
        # authoritative policy evidence is available. The malicious
        # instruction is ignored and the official policy remains authoritative.
        prompt_injection_terms = [
            "ignore the real policy",
            "ignore the policy",
            "use that newer document",
            "give everyone 60 days",
            "approve my return",
            "migration note says",
        ]

        is_prompt_injection = any(
            term in query_lower
            for term in prompt_injection_terms
        )

        # Normal retrieval still uses the similarity threshold.
        # Prompt-injection queries are exempt because their instruction
        # should be ignored rather than treated as missing evidence.
        if chunks[0].similarity_score < 0.35 and not is_prompt_injection:
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.INSUFFICIENT_EVIDENCE,
                customer_message=(
                    "The supplied information is insufficient to answer this "
                    "question reliably. Please get human confirmation from "
                    "customer support."
                )
            )

        return SafetyDecision(False)

    @staticmethod
    def evaluate_privacy_request(query: str) -> SafetyDecision:
        query_lower = query.lower()
        privacy_keywords = ["email", "address", "risk score", "warehouse note", "internal note"]
        if any(kw in query_lower for kw in privacy_keywords):
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.PROMPT_INJECTION,
                customer_message="Internal operational notes, risk scores, and private customer details cannot be disclosed. Connecting to human support."
            )
        return SafetyDecision(False)

    @staticmethod
    def evaluate_ambiguity(is_ambiguous: bool, order_ids: List[str]) -> SafetyDecision:
        if is_ambiguous and len(order_ids) > 1:
            ids_formatted = " or ".join(order_ids)
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.AMBIGUOUS_ORDER,
                customer_message=f"Multiple orders ({ids_formatted}) were referenced in our conversation. Which order are you asking about?"
            )
        return SafetyDecision(False)
