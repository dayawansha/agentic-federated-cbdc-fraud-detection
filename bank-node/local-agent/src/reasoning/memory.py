from collections import deque
from typing import Any, Deque, Dict, List, Optional


class AgentMemory:
    """Short-term and long-term memory for agentic reasoning context."""

    def __init__(self, agent_id: str, long_term_capacity: int = 50):
        self.agent_id = agent_id
        self.short_term: Deque[Dict[str, Any]] = deque(maxlen=20)
        self.long_term: Deque[Dict[str, Any]] = deque(maxlen=long_term_capacity)

    def remember(self, event: Dict[str, Any], *, long_term: bool = False) -> None:
        record = dict(event)
        record.setdefault("agent_id", self.agent_id)
        self.short_term.append(record)
        if long_term:
            self.long_term.append(record)

    def context_summary(self, short_limit: int = 5, long_limit: int = 5) -> str:
        lines: List[str] = []
        if self.long_term:
            lines.append("Long-term memory:")
            for item in list(self.long_term)[-long_limit:]:
                lines.append(f"- {item.get('summary', item)}")
        if self.short_term:
            lines.append("Short-term memory:")
            for item in list(self.short_term)[-short_limit:]:
                lines.append(f"- {item.get('summary', item)}")
        return "\n".join(lines) if lines else "No prior memory recorded."


_MEMORY_STORE: Dict[str, AgentMemory] = {}


def get_agent_memory(agent_id: str) -> AgentMemory:
    if agent_id not in _MEMORY_STORE:
        _MEMORY_STORE[agent_id] = AgentMemory(agent_id)
    return _MEMORY_STORE[agent_id]


def reset_agent_memory(agent_id: Optional[str] = None) -> None:
    if agent_id is None:
        _MEMORY_STORE.clear()
        return
    _MEMORY_STORE.pop(agent_id, None)
