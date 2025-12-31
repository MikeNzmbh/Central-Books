"""
Workflow Graph Models and Runner

Provides:
- WorkflowStepResult: Result of a single step execution
- WorkflowRunResult: Result of complete workflow run
- WorkflowGraph: DAG-based workflow orchestration with run()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# RESULT MODELS
# =============================================================================

StepStatus = Literal["pending", "running", "success", "failed", "skipped"]
WorkflowStatus = Literal["success", "partial", "failed"]


class WorkflowStepResult(BaseModel):
    """Result of a single workflow step execution."""

    step_name: str
    status: StepStatus
    started_at: datetime
    finished_at: datetime
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class WorkflowRunResult(BaseModel):
    """Result of a complete workflow run."""

    workflow_name: str
    status: WorkflowStatus
    started_at: datetime
    finished_at: datetime
    steps: List[WorkflowStepResult] = Field(default_factory=list)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    duration_ms: float = 0.0

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def success_count(self) -> int:
        """Count of successful steps."""
        return sum(1 for s in self.steps if s.status == "success")

    @property
    def failed_count(self) -> int:
        """Count of failed steps."""
        return sum(1 for s in self.steps if s.status == "failed")


# =============================================================================
# WORKFLOW GRAPH
# =============================================================================


class WorkflowGraph:
    """
    Directed acyclic graph for workflow orchestration with execution support.

    Provides:
    - Step registration with callables
    - Edge-based dependency definition
    - Topological execution via run()
    - Result collection with artifacts
    """

    def __init__(self, name: str = "unnamed_workflow"):
        """Initialize the workflow graph."""
        self.name = name
        self._steps: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._edges: Dict[str, List[str]] = {}  # from_step -> [to_steps]
        self._reverse_edges: Dict[str, List[str]] = {}  # to_step -> [from_steps]

    def add_step(
        self,
        name: str,
        fn: Callable[[Dict[str, Any]], None],
    ) -> None:
        """
        Add a step to the workflow.

        Args:
            name: Unique name for the step.
            fn: Callable that receives context dict and mutates it.
        """
        if name in self._steps:
            raise ValueError(f"Step '{name}' already exists")
        self._steps[name] = fn
        if name not in self._edges:
            self._edges[name] = []
        if name not in self._reverse_edges:
            self._reverse_edges[name] = []

    def add_edge(
        self,
        from_step: str,
        to_step: str,
    ) -> None:
        """
        Add a dependency edge from one step to another.

        Args:
            from_step: Source step (must complete first).
            to_step: Target step (runs after source).
        """
        if from_step not in self._steps:
            raise ValueError(f"Source step '{from_step}' not found")
        if to_step not in self._steps:
            raise ValueError(f"Target step '{to_step}' not found")

        if to_step not in self._edges[from_step]:
            self._edges[from_step].append(to_step)
        if from_step not in self._reverse_edges[to_step]:
            self._reverse_edges[to_step].append(from_step)

    def _topological_sort(self) -> List[str]:
        """
        Return steps in topological order (dependencies first).

        Uses Kahn's algorithm.
        """
        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {step: 0 for step in self._steps}
        for step in self._steps:
            for next_step in self._edges.get(step, []):
                in_degree[next_step] = in_degree.get(next_step, 0) + 1

        # Start with nodes that have no dependencies
        queue = [step for step, degree in in_degree.items() if degree == 0]
        result: List[str] = []

        while queue:
            # Sort for deterministic order
            queue.sort()
            current = queue.pop(0)
            result.append(current)

            for next_step in self._edges.get(current, []):
                in_degree[next_step] -= 1
                if in_degree[next_step] == 0:
                    queue.append(next_step)

        if len(result) != len(self._steps):
            raise RuntimeError("Cycle detected in workflow graph")

        return result

    def run(self, initial_context: Dict[str, Any]) -> WorkflowRunResult:
        """
        Execute the workflow steps in topological order.

        Args:
            initial_context: Initial data passed to first steps.

        Returns:
            WorkflowRunResult with per-step details and artifacts.
        """
        workflow_started = datetime.now(timezone.utc)
        context = dict(initial_context)  # Copy to avoid mutating input
        step_results: List[WorkflowStepResult] = []
        overall_status: WorkflowStatus = "success"
        workflow_error: Optional[str] = None

        try:
            execution_order = self._topological_sort()
        except RuntimeError as e:
            return WorkflowRunResult(
                workflow_name=self.name,
                status="failed",
                started_at=workflow_started,
                finished_at=datetime.now(timezone.utc),
                error_message=str(e),
            )

        failed_steps: set = set()

        for step_name in execution_order:
            step_fn = self._steps[step_name]

            # Check if dependencies failed
            dependencies = self._reverse_edges.get(step_name, [])
            deps_failed = any(dep in failed_steps for dep in dependencies)

            if deps_failed:
                # Skip step if dependencies failed
                step_results.append(
                    WorkflowStepResult(
                        step_name=step_name,
                        status="skipped",
                        started_at=datetime.now(timezone.utc),
                        finished_at=datetime.now(timezone.utc),
                        error_message="Skipped due to failed dependency",
                    )
                )
                failed_steps.add(step_name)
                continue

            # Execute step
            step_started = datetime.now(timezone.utc)
            
            # Real-time streaming
            try:
                import asyncio
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                if channel_layer:
                    message = {
                        "type": "broadcast_message",
                        "workflow": self.name,
                        "step": step_name,
                        "status": "running",
                        "timestamp": step_started.isoformat()
                    }
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(channel_layer.group_send("agent_broadcast", message))
                    except RuntimeError:
                        async_to_sync(channel_layer.group_send)("agent_broadcast", message)
            except ImportError:
                pass

            try:
                step_fn(context)
                step_finished = datetime.now(timezone.utc)

                step_results.append(
                    WorkflowStepResult(
                        step_name=step_name,
                        status="success",
                        started_at=step_started,
                        finished_at=step_finished,
                        duration_ms=(step_finished - step_started).total_seconds() * 1000,
                    )
                )

            except Exception as e:
                step_finished = datetime.now(timezone.utc)
                failed_steps.add(step_name)

                step_results.append(
                    WorkflowStepResult(
                        step_name=step_name,
                        status="failed",
                        started_at=step_started,
                        finished_at=step_finished,
                        error_message=str(e),
                        duration_ms=(step_finished - step_started).total_seconds() * 1000,
                    )
                )

        workflow_finished = datetime.now(timezone.utc)

        # Determine overall status
        success_count = sum(1 for r in step_results if r.status == "success")
        failed_count = sum(1 for r in step_results if r.status == "failed")

        if failed_count == 0:
            overall_status = "success"
        elif success_count > 0:
            overall_status = "partial"
        else:
            overall_status = "failed"

        # Collect artifacts from context
        artifact_keys = [
            "documents",
            "extracted_documents",
            "transactions",
            "journal_entries",
            "compliance_result",
            "audit_report",
        ]
        artifacts: Dict[str, Any] = {}
        for key in artifact_keys:
            if key in context:
                val = context[key]
                # Convert Pydantic models to dicts for serialization
                if hasattr(val, "model_dump"):
                    artifacts[key] = val.model_dump()
                elif isinstance(val, list):
                    artifacts[key] = [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in val
                    ]
                else:
                    artifacts[key] = val

        return WorkflowRunResult(
            workflow_name=self.name,
            status=overall_status,
            started_at=workflow_started,
            finished_at=workflow_finished,
            steps=step_results,
            artifacts=artifacts,
            duration_ms=(workflow_finished - workflow_started).total_seconds() * 1000,
        )

    def get_step_names(self) -> List[str]:
        """Get all registered step names."""
        return list(self._steps.keys())

    @property
    def step_count(self) -> int:
        """Number of registered steps."""
        return len(self._steps)

    @property
    def edge_count(self) -> int:
        """Number of edges."""
        return sum(len(targets) for targets in self._edges.values())
