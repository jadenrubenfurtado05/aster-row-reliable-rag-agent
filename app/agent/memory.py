from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ConversationTurn(BaseModel):
    """Represents a single turn in a conversation session."""
    user_message: str = Field(..., description="The user's query for this turn")
    assistant_response: str = Field(..., description="The assistant's answer for this turn")
    referenced_order_id: Optional[str] = Field(None, description="Order ID referenced in this turn if any")

class SessionMemory:
    """In-memory session store managing multi-turn conversation history."""

    def __init__(self, max_history_turns: int = 5):
        self.max_history_turns = max_history_turns
        self._sessions: Dict[str, List[ConversationTurn]] = {}

    def get_history(self, session_id: str) -> List[ConversationTurn]:
        """Returns conversation history for a given session ID."""
        return self._sessions.get(session_id, [])

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        referenced_order_id: Optional[str] = None
    ) -> None:
        """Appends a new turn to session history while enforcing maximum turn limits."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
            referenced_order_id=referenced_order_id
        )
        self._sessions[session_id].append(turn)

        # Enforce sliding window turn limit
        if len(self._sessions[session_id]) > self.max_history_turns:
            self._sessions[session_id] = self._sessions[session_id][-self.max_history_turns:]

    def resolve_order_context(self, session_id: str) -> Dict[str, Any]:
        """
        Analyzes session history to resolve referenced order IDs.
        Returns:
            {
                "active_order_id": Optional[str],
                "is_ambiguous": bool,
                "referenced_order_ids": List[str]
            }
        """
        history = self.get_history(session_id)
        if not history:
            return {"active_order_id": None, "is_ambiguous": False, "referenced_order_ids": []}

        unique_order_ids: List[str] = []
        for turn in history:
            if turn.referenced_order_id and turn.referenced_order_id not in unique_order_ids:
                unique_order_ids.append(turn.referenced_order_id)

        if not unique_order_ids:
            return {"active_order_id": None, "is_ambiguous": False, "referenced_order_ids": []}

        if len(unique_order_ids) == 1:
            return {
                "active_order_id": unique_order_ids[0],
                "is_ambiguous": False,
                "referenced_order_ids": unique_order_ids
            }
        else:
            return {
                "active_order_id": None,
                "is_ambiguous": True,
                "referenced_order_ids": unique_order_ids
            }

    def clear_session(self, session_id: str) -> None:
        """Clears session history for a given session ID."""
        if session_id in self._sessions:
            del self._sessions[session_id]
