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
    def evaluate_rag_safety(rag_result: Optional[RAGSearchResult]) -> SafetyDecision:
        if not rag_result:
            return SafetyDecision(False)

        if rag_result.conflict_detected:
            sources_str = ", ".join(rag_result.conflicting_sources)
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.POLICY_CONFLICT,
                customer_message=f"Our official documents contain conflicting guidance regarding this topic ({sources_str}). Please confirm with human customer support."
            )

        # Low evidence check
        if not rag_result.retrieved_chunks or rag_result.retrieved_chunks[0].similarity_score < 0.35:
            return SafetyDecision(
                handoff_required=True,
                reason_code=HandoffReason.INSUFFICIENT_EVIDENCE,
                customer_message="The available company information does not provide a reliable answer to your question. Please contact human support."
            )

        return SafetyDecision(False)

    @staticmethod
    def evaluate_privacy_request(query: str) -> SafetyDecision:
        query_lower = query.lower()
        privacy_keywords = ["email", "address", "risk score", "warehouse note", "internal note", "hidden prompt"]
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
