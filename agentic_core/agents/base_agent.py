"""
Base Agent Framework

This module provides the foundational BaseAgent class that all specialized
agents inherit from. It handles:

- Agent execution lifecycle
- LLM call logging and tracing
- Tool/function call recording
- Async compatibility
- Error handling and recovery

Example usage:
    class MyAgent(BaseAgent):
        agent_name = "my_agent"
        
        async def run(self, input_data: dict) -> dict:
            # Agent logic here
            result = await self.call_llm("Analyze this...")
            return {"result": result}
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Optional, TypeVar

from agentic_core.models.base import AgentTrace, LLMCallMetadata

T = TypeVar("T")


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.

    Provides common functionality for:
    - Execution tracing and observability
    - LLM call management and logging
    - Tool invocation recording
    - Async/sync execution support

    Subclasses must implement:
    - run(): The main agent logic

    Attributes:
        agent_name: Unique name for this agent type.
        agent_version: Version string for this agent.
        trace: Current execution trace (set during run).
        llm_client: Optional LLM client for making calls.
        default_model: Default model to use for LLM calls.
        max_retries: Maximum retries for failed LLM calls.
        tools: Registered tools/functions the agent can use.
    """

    agent_name: str = "base_agent"
    agent_version: str = "0.1.0"

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        default_model: str = "gpt-4",
        max_retries: int = 3,
    ):
        """
        Initialize the base agent.

        Args:
            llm_client: Optional OpenAI-compatible client for LLM calls.
            default_model: Default model to use.
            max_retries: Maximum retries for failed API calls.
        """
        self.llm_client = llm_client
        self.default_model = default_model
        self.max_retries = max_retries
        self.trace: Optional[AgentTrace] = None
        self.tools: dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        """
        Register a tool/function that this agent can use.

        Args:
            name: Unique name for the tool.
            func: The callable to execute.
        """
        self.tools[name] = func

    def _create_trace(self, input_summary: Optional[str] = None) -> AgentTrace:
        """Create a new trace for this run."""
        return AgentTrace(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            input_summary=input_summary,
        )

    async def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Make an LLM call with automatic logging and retry.

        Args:
            prompt: The user/main prompt.
            system_prompt: Optional system prompt.
            model: Model to use (defaults to self.default_model).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            stop: Stop sequences.
            **kwargs: Additional arguments for the API.

        Returns:
            The LLM response text.

        Raises:
            RuntimeError: If no LLM client is configured.
            Exception: If all retries fail.
        """
        if self.llm_client is None:
            # In placeholder mode, return a mock response
            self._log_llm_call(
                model=model or self.default_model,
                system_prompt=system_prompt,
                user_prompt=prompt,
                response_text="[PLACEHOLDER: No LLM client configured]",
                latency_ms=0,
                error="No LLM client configured",
            )
            return "[PLACEHOLDER: No LLM client configured]"

        model = model or self.default_model
        start_time = time.time()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                # Build messages
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                # Make the API call
                response = await self._async_llm_call(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop=stop,
                    **kwargs,
                )

                # Extract response text
                response_text = self._extract_response_text(response)
                latency_ms = (time.time() - start_time) * 1000

                # Log the call
                self._log_llm_call(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    response_text=response_text,
                    latency_ms=latency_ms,
                    prompt_tokens=getattr(response, "usage", {}).get(
                        "prompt_tokens", 0
                    ),
                    completion_tokens=getattr(response, "usage", {}).get(
                        "completion_tokens", 0
                    ),
                )

                return response_text

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue

        # All retries failed
        error_msg = str(last_error) if last_error else "Unknown error"
        self._log_llm_call(
            model=model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            response_text=None,
            latency_ms=(time.time() - start_time) * 1000,
            error=error_msg,
        )
        raise last_error or RuntimeError("LLM call failed after all retries")

    async def _async_llm_call(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        """
        Make the actual async LLM API call.

        Override this method to support different LLM providers.
        """
        # Default implementation for OpenAI-compatible clients
        if hasattr(self.llm_client, "chat"):
            return await self.llm_client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
        raise NotImplementedError(
            "LLM client does not have expected interface. "
            "Override _async_llm_call for custom clients."
        )

    def _extract_response_text(self, response: Any) -> str:
        """Extract text from LLM response object."""
        # OpenAI-style response
        if hasattr(response, "choices") and response.choices:
            return response.choices[0].message.content or ""
        # Dict-style response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
        return str(response)

    def _log_llm_call(
        self,
        model: str,
        system_prompt: Optional[str],
        user_prompt: str,
        response_text: Optional[str],
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Log an LLM call to the current trace."""
        if self.trace is None:
            return

        call = LLMCallMetadata(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_text=response_text,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            error=error,
        )
        self.trace.add_llm_call(call)

    async def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Call a registered tool and log the invocation.

        Args:
            tool_name: Name of the tool to call.
            **kwargs: Arguments to pass to the tool.

        Returns:
            The tool's return value.

        Raises:
            ValueError: If the tool is not registered.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' is not registered")

        tool = self.tools[tool_name]
        
        try:
            # Handle async tools
            if asyncio.iscoroutinefunction(tool):
                result = await tool(**kwargs)
            else:
                result = tool(**kwargs)

            # Log the tool call
            if self.trace:
                self.trace.add_tool_call(
                    tool_name=tool_name,
                    args=kwargs,
                    result=result,
                )

            return result

        except Exception as e:
            # Log failed tool call
            if self.trace:
                self.trace.add_tool_call(
                    tool_name=tool_name,
                    args=kwargs,
                    result={"error": str(e)},
                )
            raise

    def log_step(self, description: str) -> None:
        """
        Log a reasoning/execution step.

        Args:
            description: Description of what the agent is doing.
        """
        if self.trace:
            self.trace.add_step(description)

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the agent's main logic.

        Subclasses must implement this method with their specific
        processing logic.

        Returns:
            Agent-specific output data.
        """
        raise NotImplementedError("Subclasses must implement run()")

    async def execute(
        self,
        *args: Any,
        input_summary: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Any, AgentTrace]:
        """
        Execute the agent with full tracing.

        This is the primary entry point for running an agent.
        It handles trace creation, execution, and finalization.

        Args:
            *args: Arguments to pass to run().
            input_summary: Optional summary of input for the trace.
            **kwargs: Keyword arguments to pass to run().

        Returns:
            Tuple of (agent result, execution trace).
        """
        self.trace = self._create_trace(input_summary)
        self.trace.status = "running"

        try:
            result = await self.run(*args, **kwargs)
            self.trace.complete(status="success")
            self.trace.output_summary = str(result)[:500]  # Truncate if needed
            return result, self.trace

        except Exception as e:
            self.trace.complete(status="error", error=str(e))
            raise

        finally:
            # Ensure trace is always available
            trace = self.trace
            self.trace = None
            if trace:
                return result if "result" in dir() else None, trace

    def execute_sync(
        self,
        *args: Any,
        input_summary: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[Any, AgentTrace]:
        """
        Synchronous wrapper for execute().

        Useful when calling from non-async code.
        """
        return asyncio.run(
            self.execute(*args, input_summary=input_summary, **kwargs)
        )
