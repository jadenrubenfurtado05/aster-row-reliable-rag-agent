from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class RetrievedChunk(BaseModel):
    """Schema representing a passage/chunk retrieved from the Knowledge Base."""
    source_filename: str = Field(..., description="Filename of the source Markdown document")
    document_id: Optional[str] = Field(None, description="Document ID from YAML front matter if available")
    title: Optional[str] = Field(None, description="Document title from YAML front matter")
    heading: str = Field(..., description="Markdown heading context for the passage")
    text: str = Field(..., description="Content text of the retrieved passage")
    similarity_score: float = Field(..., description="Vector or hybrid retrieval similarity score")
    status: str = Field(..., description="Document status: 'active', 'superseded', or 'draft'")
    policy_authority: str = Field(..., description="Policy authority: 'official' or 'none'")
    audience: str = Field(..., description="Audience tag: 'customer' or 'internal'")
    effective_date: Optional[str] = Field(None, description="Effective date string from front matter")
    last_reviewed: Optional[str] = Field(None, description="Last reviewed date string from front matter")
    supersedes: Optional[str] = Field(None, description="Document ID superseded by this document")

    @property
    def citation(self) -> str:
        """Returns standard citation format: [filename#heading]."""
        return f"{self.source_filename}#{self.heading}"

class RAGSearchResult(BaseModel):
    """Schema representing the complete result of a RAG retrieval operation."""
    query: str = Field(..., description="The user query")
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list, description="List of authoritative retrieved chunks")
    conflict_detected: bool = Field(False, description="Whether active authoritative sources conflict")
    conflicting_sources: List[str] = Field(default_factory=list, description="Filenames of conflicting sources if conflict detected")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Structured diagnostics tracing candidate evaluation and exclusion reasons")

class SanitizedOrderResult(BaseModel):
    """Schema representing a customer-safe order lookup result."""
    order_id: str = Field(..., description="Normalized order ID (e.g. 'ORD-1007')")
    found: bool = Field(True, description="Whether the order was found in the repository")
    status: str = Field(..., description="Authoritative order status")
    membership_tier: Optional[str] = Field(None, description="Customer membership tier if applicable")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Customer-safe line items")
    placed_at: Optional[str] = Field(None, description="Order placement timestamp")
    status_updated_at: Optional[str] = Field(None, description="Status update timestamp")
    shipped_at: Optional[str] = Field(None, description="Shipment timestamp if shipped")
    delivered_at: Optional[str] = Field(None, description="Delivery timestamp if delivered")
    carrier: Optional[str] = Field(None, description="Valid carrier name")
    tracking_number: Optional[str] = Field(None, description="Tracking number if valid")
    estimated_delivery: Optional[str] = Field(None, description="Delivery estimate if valid and status is active")
    customer_safe_message: Optional[str] = Field(None, description="Pre-formatted safe message")
    handoff_required: bool = Field(False, description="Whether operational exception requires human handoff")
    handoff_reason: Optional[str] = Field(None, description="Reason for handoff if required")
    action_supported: bool = Field(True, description="Whether the requested operation is supported by the lookup tool")

class AgentResponse(BaseModel):
    """Schema representing the final agent output for a user turn."""
    answer: str = Field(..., description="Final text answer generated for the user")
    sources: List[str] = Field(default_factory=list, description="List of source citations formatted as filename#heading")
    handoff: bool = Field(False, description="Whether human support handoff is recommended")
    handoff_reason: Optional[str] = Field(None, description="Reason for recommending human handoff")
    tool_used: Optional[str] = Field(None, description="Name of tool executed during turn, if any")
    trace_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional structured trace / debugging metadata")
