"""
Operations Agent - AI Employee for Business Operations

Handles:
- Workflow run summarization and analysis
- Retry plan generation for failed jobs
- Process optimization recommendations
- Operational report generation
"""

from typing import Any, List, Optional

from agentic_core.agents.base_agent import BaseAgent
from agentic_core.models.base import AgentTrace
from agentic.agents.shared.profile import AgentProfile


class OperationsAgent(BaseAgent):
    """
    AI Employee for business operations and process automation.

    Capabilities:
    - Summarize workflow execution traces
    - Propose retry plans for failed operations
    - Generate operational insights
    - Monitor process health

    This agent has MEDIUM risk level as it can influence
    business process decisions.
    """

    agent_name = "operations_agent"
    agent_version = "0.1.0"

    # Static profile defining this agent's identity and capabilities
    profile = AgentProfile(
        name="Operations Agent",
        role="operations",
        description=(
            "AI employee responsible for business operations automation. "
            "Monitors workflows, summarizes execution traces, proposes retry "
            "strategies for failed jobs, and generates operational insights."
        ),
        capabilities=[
            "summarize_workflow_run",
            "propose_retry_plan",
            "analyze_process_bottlenecks",
            "generate_operations_report",
            "triage_failed_jobs",
            "recommend_process_improvements",
        ],
        max_parallel_tasks=5,
        risk_level="medium",
        llm_model="gpt-4.1-mini",
        system_prompt=(
            "You are an Operations AI assistant. Your role is to monitor business "
            "processes, analyze workflow executions, and provide actionable insights "
            "to improve operational efficiency. Be concise, data-driven, and focus on "
            "practical recommendations."
        ),
        tools=[
            "workflow_status_checker",
            "log_analyzer",
            "metrics_aggregator",
        ],
        owner_team="platform",
    )

    def __init__(self, llm_client: Optional[Any] = None, **kwargs: Any):
        """Initialize the Operations Agent."""
        super().__init__(llm_client=llm_client, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Default run method - delegates to specific capability methods."""
        self.log_step("OperationsAgent.run() called - use specific methods instead")
        return {"status": "use_specific_methods"}

    async def summarize_workflow_run(self, trace: AgentTrace) -> str:
        """
        Summarize a workflow execution trace.

        Args:
            trace: The execution trace from a workflow run.

        Returns:
            Human-readable summary of the workflow execution.
        """
        self.log_step(f"Summarizing workflow trace: {trace.trace_id}")

        # Build prompt spec (no actual LLM call yet)
        prompt_spec = {
            "task": "summarize_workflow",
            "trace_id": trace.trace_id,
            "agent_name": trace.agent_name,
            "status": trace.status,
            "duration_ms": trace.duration_ms,
            "llm_calls_count": len(trace.llm_calls),
            "steps_count": len(trace.steps),
            "error": trace.error,
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        # Deterministic mock response for testing
        if trace.status == "success":
            summary = (
                f"Workflow '{trace.agent_name}' completed successfully in "
                f"{trace.duration_ms:.1f}ms. Executed {len(trace.steps)} steps "
                f"with {len(trace.llm_calls)} LLM calls. "
                f"Total tokens used: {trace.total_tokens_used}."
            )
        elif trace.status == "error":
            summary = (
                f"Workflow '{trace.agent_name}' failed after {trace.duration_ms:.1f}ms. "
                f"Error: {trace.error or 'Unknown error'}. "
                f"Completed {len(trace.steps)} steps before failure."
            )
        else:
            summary = (
                f"Workflow '{trace.agent_name}' status: {trace.status}. "
                f"Duration: {trace.duration_ms:.1f}ms, Steps: {len(trace.steps)}."
            )

        return summary

    async def propose_retry_plan(self, errors: List[str]) -> List[str]:
        """
        Propose a retry plan for a list of errors.

        Args:
            errors: List of error messages from failed operations.

        Returns:
            List of recommended retry actions.
        """
        self.log_step(f"Proposing retry plan for {len(errors)} errors")

        # Build prompt spec
        prompt_spec = {
            "task": "propose_retry",
            "error_count": len(errors),
            "errors": errors[:5],  # First 5 for context
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        # Deterministic mock response
        retry_plan: List[str] = []

        for i, error in enumerate(errors, 1):
            error_lower = error.lower()

            if "timeout" in error_lower:
                retry_plan.append(f"Step {i}: Increase timeout and retry with exponential backoff")
            elif "connection" in error_lower or "network" in error_lower:
                retry_plan.append(f"Step {i}: Wait 30s for network recovery, then retry")
            elif "rate limit" in error_lower:
                retry_plan.append(f"Step {i}: Implement rate limiting, wait 60s, then retry")
            elif "auth" in error_lower or "permission" in error_lower:
                retry_plan.append(f"Step {i}: Refresh credentials before retry")
            elif "not found" in error_lower:
                retry_plan.append(f"Step {i}: Verify resource exists, skip if missing")
            else:
                retry_plan.append(f"Step {i}: Log error for manual review, skip and continue")

        if not retry_plan:
            retry_plan.append("No specific retry actions identified - escalate to engineering")

        return retry_plan

    async def analyze_process_bottlenecks(
        self,
        step_durations: List[dict],
    ) -> dict:
        """
        Analyze workflow steps for bottlenecks.

        Args:
            step_durations: List of {"name": str, "duration_ms": float} dicts.

        Returns:
            Analysis with identified bottlenecks and recommendations.
        """
        self.log_step(f"Analyzing {len(step_durations)} steps for bottlenecks")

        if not step_durations:
            return {"bottlenecks": [], "recommendations": ["No steps to analyze"]}

        # Calculate statistics
        total_duration = sum(s.get("duration_ms", 0) for s in step_durations)
        avg_duration = total_duration / len(step_durations) if step_durations else 0

        # Find bottlenecks (steps taking >50% of total or >2x average)
        bottlenecks = []
        for step in step_durations:
            duration = step.get("duration_ms", 0)
            if duration > total_duration * 0.5 or duration > avg_duration * 2:
                bottlenecks.append({
                    "step": step.get("name", "unknown"),
                    "duration_ms": duration,
                    "percentage": (duration / total_duration * 100) if total_duration else 0,
                })

        recommendations = []
        for bn in bottlenecks:
            recommendations.append(
                f"Optimize '{bn['step']}' - takes {bn['percentage']:.1f}% of total time"
            )

        if not bottlenecks:
            recommendations.append("No significant bottlenecks detected")

        return {
            "total_duration_ms": total_duration,
            "average_step_ms": avg_duration,
            "bottlenecks": bottlenecks,
            "recommendations": recommendations,
        }
