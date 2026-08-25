import os
from typing import Optional, Protocol
from app.config import get_config

class BaseLLMClient(Protocol):
    """Protocol for LLM client implementations."""
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        ...

class GoogleGenAIClient:
    """Google GenAI SDK client integration."""
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.llm_api_key
        self.model_name = model or config.llm_model
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key or not self.client:
            raise ValueError("LLM API key is not configured or client initialization failed.")

        try:
            from google import genai
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                )
            )
            if response and response.text:
                return response.text.strip()
            return ""
        except Exception as e:
            raise RuntimeError(f"Google GenAI API call failed: {str(e)}") from e


class MockLLMClient:
    """Mock LLM client for deterministic unit testing without live API calls."""
    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response
        self.last_system_prompt: Optional[str] = None
        self.last_user_prompt: Optional[str] = None

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt

        if self.canned_response:
            return self.canned_response

        prompt_lower = user_prompt.lower()
        query_text = prompt_lower
        if "user query:" in prompt_lower:
            query_text = prompt_lower.split("user query:")[1].split("\n")[0]

        if "conflict_warning" in prompt_lower:
            return "Our official documents contain conflicting guidance regarding this item. One document says hand-wash the body while another says all components are dishwasher safe. Please contact human support for confirmation. [11-product-care.md#Breeze Tumbler] [12-breeze-tumbler-product-card.md#Cleaning]"
        elif "ord-1011" in prompt_lower or "ord-1011" in query_text:
            return "Order ORD-1011 has shipped with Canada Post. A delivery estimate is unavailable at this time."
        elif "ord-1004" in prompt_lower or '"status": "cancelled"' in prompt_lower:
            return "The order is cancelled and will not be shipped."
        elif "ord-1007" in prompt_lower or "ord-1007" in query_text:
            return "Your order ORD-1007 has shipped with UPS and is currently estimated to arrive on August 22, 2026."
        elif any(w in query_text for w in ["damaged", "defective", "broken zipper", "out of luck"]):
            return "Final sale does not block damaged-item review. Please report within 7 days of delivery. Human review before approval is required. [03-final-sale-and-promotions.md#Damaged or incorrect items] [04-damaged-or-wrong-items.md#Reporting window]"
        elif "trailplus" in query_text:
            return "TrailPlus members receive a 45 calendar days return window from delivery for eligible items. [09-trailplus-membership.md#Return window]"
        elif "germany" in query_text:
            return "Aster & Row currently ships internationally only to Canada. Shipping to Germany is not currently available. [06-international-shipping.md#Supported destinations]"
        elif "canada" in query_text:
            return "Canada is supported. Canadian orders generally arrive within 5–9 business days after dispatch. Import duties or taxes are not prepaid by Aster & Row. [06-international-shipping.md#Supported destinations]"
        elif "lifetime warranty" in query_text or "lifetime" in query_text:
            return "Aster & Row has no lifetime warranty. Bags have 2 years from purchase date, while drinkware and travel accessories have 1 year from purchase date. [07-warranty.md#Warranty periods]"
        elif "migration note" in query_text or "60 days" in query_text or "approve" in query_text:
            return "The content migration note is not authoritative customer policy. Standard policy is 30 calendar days unless a valid exception applies. The agent cannot approve a return without human review. [01-returns-policy-current.md#Standard return window]"
        elif "standard" in query_text or "return window" in query_text or "backpack" in query_text or "return" in query_text:
            return "Customers on the standard plan may request a return within 30 calendar days of delivery. [01-returns-policy-current.md#Standard return window]"
        elif "action_supported: false" in prompt_lower or "cancel" in query_text:
            return "Order cancellation is not supported directly through this chat. Please contact human support to request cancellation."
        elif "no_evidence" in prompt_lower or "insufficient" in prompt_lower:
            return "The supplied information is insufficient to answer your query reliably. Please contact human support."
        else:
            return "Based on Aster & Row policy reference data, here is the information requested."
