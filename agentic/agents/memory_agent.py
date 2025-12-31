"""
Memory Agent - Specializes in managing the shared vector context.
"""

from typing import Any, Optional
from agentic_core.agents.base_agent import BaseAgent

class MemoryAgent(BaseAgent):
    agent_name = "memory_agent"
    agent_version = "0.1.0"

    async def run(self, action: str, text: Optional[str] = None, query: Optional[str] = None, metadata: Optional[dict] = None) -> Any:
        """
        Perform memory actions.
        """
        if action == "store" and text:
            self.memorize(text, metadata)
            return {"status": "stored"}
        elif action == "recall" and query:
            context = await self.recall(query)
            return {"context": context}
        else:
            return {"error": "Invalid action or missing parameters"}
