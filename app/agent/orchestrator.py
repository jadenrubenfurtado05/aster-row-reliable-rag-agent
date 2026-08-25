import json
import re
from typing import Any, Dict, List, Optional
from app.config import get_config
from app.schemas import AgentResponse, RAGSearchResult, SanitizedOrderResult
from app.rag.retriever import RAGRetriever
from app.tools.order_lookup import OrderLookupTool
from app.agent.llm_client import BaseLLMClient, GoogleGenAIClient, MockLLMClient
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.memory import ConversationTurn, SessionMemory
from app.safety.guardrails import HandoffReason, SafetyDecision, SafetyGuardrails

class AgentOrchestrator:
    """Orchestrates RAG retrieval, order lookup tool execution, session memory, and LLM reasoning."""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        rag_retriever: Optional[RAGRetriever] = None,
        order_tool: Optional[OrderLookupTool] = None,
        session_memory: Optional[SessionMemory] = None
    ):
        config = get_config()
        self.rag_retriever = rag_retriever or RAGRetriever()
        self.order_tool = order_tool or OrderLookupTool()
        self.session_memory = session_memory or SessionMemory()

        if llm_client is not None:
            self.llm_client = llm_client
        else:
            if config.llm_api_key:
                self.llm_client = GoogleGenAIClient()
            else:
                self.llm_client = MockLLMClient()

    def process_query(self, user_query: str, session_id: str = "default") -> AgentResponse:
        """Processes a user query within a session context, enforcing memory and safety guardrails."""
        # 1. Check for Privacy/Security violations
        privacy_safety = SafetyGuardrails.evaluate_privacy_request(user_query)

        # 2. Parse Order ID and action intent from current query
        order_id_match = re.search(r"(?i)\b(ORD-\d+|ord-\d+)\b", user_query)
        detected_order_id = order_id_match.group(1).upper() if order_id_match else None

        query_lower = user_query.lower()
        is_order_followup = any(phrase in query_lower for phrase in ["when", "where", "arrive", "status", "order", "track", "pkg", "package"])
        is_write_action = any(verb in query_lower for verb in ["cancel", "cancellation", "change address", "update address", "refund", "replace"])
        action_name = "cancel" if "cancel" in query_lower else ("change_address" if "address" in query_lower else "lookup")

        # Handle explicit order query missing an order ID
        policy_keywords = [
            "policy", "return", "window", "ship", "shipping", "canada", "germany",
            "warranty", "clean", "care", "tumbler", "breeze", "gift card", "fee", "days",
            "final-sale", "final sale", "zipper", "damaged", "defective", "broken",
            "trailplus", "membership", "migration", "note", "country", "destination",
            "international", "adhesive", "vegan"
        ]
        has_policy_query = any(kw in query_lower for kw in policy_keywords)

        if not detected_order_id and is_order_followup and not has_policy_query:
            context_res = self.session_memory.resolve_order_context(session_id)
            if not context_res["active_order_id"] and not context_res["is_ambiguous"]:
                response = AgentResponse(
                    answer="Please provide your order ID so I can assist you.",
                    sources=[],
                    handoff=False,
                    tool_used=None,
                    trace_metadata={"session_id": session_id, "detected_order_id": detected_order_id, "missing_order_id": True}
                )
                self.session_memory.add_turn(session_id, user_query, response.answer)
                return response

        # 3. Memory Context Resolution (for implicit follow-up queries without explicit Order ID)
        if not detected_order_id and is_order_followup:
            context_res = self.session_memory.resolve_order_context(session_id)
            if context_res["is_ambiguous"]:
                ambiguity_decision = SafetyGuardrails.evaluate_ambiguity(True, context_res["referenced_order_ids"])
                response = AgentResponse(
                    answer=ambiguity_decision.customer_message or "Multiple orders were referenced. Which order are you inquiring about?",
                    sources=[],
                    handoff=True,
                    handoff_reason=ambiguity_decision.reason_code.value if ambiguity_decision.reason_code else HandoffReason.AMBIGUOUS_ORDER.value,
                    tool_used=None,
                    trace_metadata={"session_id": session_id, "ambiguous_order_ids": context_res["referenced_order_ids"]}
                )
                self.session_memory.add_turn(session_id, user_query, response.answer)
                return response
            elif context_res["active_order_id"]:
                detected_order_id = context_res["active_order_id"]

        # 4. Determine Routing
        has_policy_query = any(kw in query_lower for kw in policy_keywords) or (detected_order_id is None)

        use_order_tool = detected_order_id is not None
        use_rag = has_policy_query or (detected_order_id is None)

        order_result: Optional[SanitizedOrderResult] = None
        rag_result: Optional[RAGSearchResult] = None
        citations: List[str] = []
        tool_used: Optional[str] = None
        handoff_flag = privacy_safety.handoff_required
        handoff_reasons: List[str] = [privacy_safety.reason_code.value] if privacy_safety.reason_code else []

        # 5. Execute Order Tool if needed
        if use_order_tool and detected_order_id:
            tool_used = "order_lookup"
            tool_action = action_name if is_write_action else "lookup"
            order_result = self.order_tool.lookup_order(detected_order_id, action=tool_action)

            order_safety = SafetyGuardrails.evaluate_order_safety(order_result)
            if order_safety.handoff_required:
                handoff_flag = True
                if order_safety.reason_code and order_safety.reason_code.value not in handoff_reasons:
                    handoff_reasons.append(order_safety.reason_code.value)

        # 6. Execute RAG Retriever if needed
        if use_rag:
            rag_result = self.rag_retriever.retrieve(user_query, top_k=5)

            if rag_result.retrieved_chunks:
                seen_citations = set()
                for chunk in rag_result.retrieved_chunks:
                    if chunk.citation not in seen_citations:
                        seen_citations.add(chunk.citation)
                        citations.append(chunk.citation)

            # Damaged item reports require human specialist review before approval
            if rag_result.retrieved_chunks and any("04-damaged-or-wrong-items.md" in c.source_filename for c in rag_result.retrieved_chunks):
                if any(w in query_lower for w in ["damaged", "broken", "defective", "wrong"]):
                    handoff_flag = True
                    if HandoffReason.UNSUPPORTED_ACTION.value not in handoff_reasons:
                        handoff_reasons.append(HandoffReason.UNSUPPORTED_ACTION.value)

            rag_safety = SafetyGuardrails.evaluate_rag_safety(rag_result, user_query)
            if rag_safety.handoff_required:
                handoff_flag = True
                if rag_safety.reason_code and rag_safety.reason_code.value not in handoff_reasons:
                    handoff_reasons.append(rag_safety.reason_code.value)

        # 6. Format LLM Input Context (including conversation history)
        history_turns = self.session_memory.get_history(session_id)
        llm_user_prompt = self._build_llm_prompt(
            user_query=user_query,
            history=history_turns,
            rag_result=rag_result,
            order_result=order_result,
            conflict_detected=rag_result.conflict_detected if rag_result else False,
            conflicting_sources=rag_result.conflicting_sources if rag_result else []
        )

        # 7. Invoke LLM safely
        try:
            raw_answer = self.llm_client.generate_response(SYSTEM_PROMPT, llm_user_prompt)
        except Exception as e:
            fallback_resp = AgentResponse(
                answer="I'm sorry, but I am currently unable to process your request due to a service connection issue. Please contact human support for assistance.",
                sources=citations,
                handoff=True,
                handoff_reason=HandoffReason.LLM_FAILURE.value,
                tool_used=tool_used,
                trace_metadata={"error": str(e), "query": user_query, "session_id": session_id}
            )
            self.session_memory.add_turn(session_id, user_query, fallback_resp.answer, referenced_order_id=detected_order_id)
            return fallback_resp

        # 8. Construct Final Structured AgentResponse
        final_handoff_reason = "; ".join(handoff_reasons) if handoff_reasons else None

        trace_metadata: Dict[str, Any] = {
            "session_id": session_id,
            "query": user_query,
            "detected_order_id": detected_order_id,
            "use_order_tool": use_order_tool,
            "use_rag": use_rag,
            "conflict_detected": rag_result.conflict_detected if rag_result else False,
            "conflicting_sources": rag_result.conflicting_sources if rag_result else [],
            "order_found": order_result.found if order_result else None,
            "action_supported": order_result.action_supported if order_result else None
        }

        response = AgentResponse(
            answer=raw_answer,
            sources=citations,
            handoff=handoff_flag,
            handoff_reason=final_handoff_reason,
            tool_used=tool_used,
            trace_metadata=trace_metadata
        )

        # Save turn to session memory
        self.session_memory.add_turn(session_id, user_query, response.answer, referenced_order_id=detected_order_id)
        return response

    def _build_llm_prompt(
        self,
        user_query: str,
        history: List[ConversationTurn],
        rag_result: Optional[RAGSearchResult],
        order_result: Optional[SanitizedOrderResult],
        conflict_detected: bool,
        conflicting_sources: List[str]
    ) -> str:
        prompt_parts: List[str] = []

        if history:
            prompt_parts.append("--- BEGIN CONVERSATION HISTORY DATA (UNTRUSTED REFERENCE ONLY) ---")
            for turn in history:
                prompt_parts.append(f"User: {turn.user_message}\nAssistant: {turn.assistant_response}")
            prompt_parts.append("--- END CONVERSATION HISTORY DATA ---\n")

        prompt_parts.append(f"USER QUERY: {user_query}\n")

        if rag_result and rag_result.retrieved_chunks:
            prompt_parts.append("--- BEGIN RETRIEVED KNOWLEDGE DATA (UNTRUSTED REFERENCE ONLY) ---")
            for chunk in rag_result.retrieved_chunks:
                prompt_parts.append(f"SOURCE: [{chunk.citation}]\nCONTENT:\n{chunk.text}\n")
            prompt_parts.append("--- END RETRIEVED KNOWLEDGE DATA ---\n")
        elif rag_result and not rag_result.retrieved_chunks:
            prompt_parts.append("--- RETRIEVED KNOWLEDGE DATA: NO_EVIDENCE_FOUND ---\n")

        if order_result:
            prompt_parts.append("--- BEGIN SANITIZED ORDER DATA (UNTRUSTED REFERENCE ONLY) ---")
            prompt_parts.append(json.dumps(order_result.model_dump(), indent=2))
            prompt_parts.append("--- END SANITIZED ORDER DATA ---\n")

        if conflict_detected:
            prompt_parts.append(
                f"--- CONFLICT WARNING ---\n"
                f"Active official sources conflict regarding this topic: {', '.join(conflicting_sources)}. "
                f"Do not silently pick one source. State that official information conflicts and recommend human confirmation."
            )

        return "\n".join(prompt_parts)
