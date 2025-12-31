"""
Base models for agent tracing and LLM call metadata.

These models provide the foundation for observability and debugging
across all agents in the system. Every agent run produces an AgentTrace
that captures LLM calls, tool invocations, and execution metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LLMCallMetadata(BaseModel):
    """
    Metadata for a single LLM API call.

    Captures the request/response pair along with timing and token usage
    for cost tracking and debugging purposes.

    Attributes:
        call_id: Unique identifier for this LLM call.
        model: The model identifier (e.g., "gpt-4", "gpt-4-turbo").
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Total tokens used (prompt + completion).
        latency_ms: Time taken for the API call in milliseconds.
        timestamp: When the call was made.
        system_prompt: The system prompt used (if any).
        user_prompt: The user prompt / input message.
        response_text: The raw response text from the LLM.
        function_calls: Any function/tool calls made by the LLM.
        error: Error message if the call failed.
    """

    call_id: str = Field(default_factory=lambda: str(uuid4()))
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    response_text: Optional[str] = None
    function_calls: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentTrace(BaseModel):
    """
    Complete execution trace for an agent run.

    This model captures everything that happened during an agent's execution,
    enabling full observability, debugging, and audit trails.

    Attributes:
        trace_id: Unique identifier for this trace.
        agent_name: Name/type of the agent that produced this trace.
        agent_version: Version of the agent code.
        started_at: When the agent run started.
        ended_at: When the agent run completed (or failed).
        duration_ms: Total execution time in milliseconds.
        status: Final status ("success", "error", "timeout", "cancelled").
        input_summary: Brief summary of the input data.
        output_summary: Brief summary of the output data.
        llm_calls: List of all LLM calls made during execution.
        tool_calls: List of tool/function invocations with their results.
        steps: Ordered list of reasoning steps taken.
        error: Error message if the agent failed.
        metadata: Additional key-value metadata.
    """

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_name: str
    agent_version: str = "0.1.0"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "pending"  # pending, running, success, error, handoff, timeout, cancelled
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    llm_calls: list[LLMCallMetadata] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def add_llm_call(self, call: LLMCallMetadata) -> None:
        """Add an LLM call to this trace."""
        self.llm_calls.append(call)

    def add_tool_call(
        self, tool_name: str, args: dict[str, Any], result: Any
    ) -> None:
        """Record a tool/function invocation."""
        self.tool_calls.append(
            {
                "tool_name": tool_name,
                "arguments": args,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def add_step(self, description: str) -> None:
        """Record a reasoning step."""
        self.steps.append(description)

    def complete(self, status: str = "success", error: Optional[str] = None) -> None:
        """Mark the trace as complete."""
        self.ended_at = datetime.utcnow()
        self.duration_ms = (
            (self.ended_at - self.started_at).total_seconds() * 1000
        )
        self.status = status
        if error:
            self.error = error

    @property
    def total_tokens_used(self) -> int:
        """Sum of all tokens used across LLM calls."""
        return sum(call.total_tokens for call in self.llm_calls)

    @property
    def total_llm_latency_ms(self) -> float:
        """Sum of all LLM call latencies."""
        return sum(call.latency_ms for call in self.llm_calls)
