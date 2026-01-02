"""
Supervisor Agent - Autonomous Workflow Orchestrator

The Supervisor Agent manages and monitors all other agents and workflows:
- Detects workflow failures
- Retries failed steps
- Reassigns tasks to different agents
- Summarizes workflow outcomes
- Maintains safety rules
- Produces human-readable logs

System Prompt:
--------------
You are the Supervisor Agent for an accounting automation system.
Your role is to:
1. Monitor all active workflows for failures or anomalies
2. Decide whether to retry, escalate, or skip failed steps
3. Ensure safety rules are maintained (no direct money movement)
4. Summarize workflow outcomes for human review
5. Coordinate between specialized agents when needed

Always prioritize:
- Data integrity over speed
- Clear audit trails over automation
- Human escalation for high-risk decisions
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging

from agentic.agents.messaging import (
    AgentMessage,
    MessageType,
    MessagePriority,
    get_message_bus,
    send_message,
    alert_agent,
)


logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND MODELS
# =============================================================================


class WorkflowStatus(str, Enum):
    """Status of a monitored workflow."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class DecisionType(str, Enum):
    """Types of supervisor decisions."""
    RETRY = "retry"
    SKIP = "skip"
    ESCALATE = "escalate"
    REASSIGN = "reassign"
    ABORT = "abort"
    CONTINUE = "continue"


@dataclass
class SupervisorDecision:
    """
    A decision made by the supervisor about a workflow issue.
    """
    decision_type: DecisionType
    reason: str
    target_step: Optional[str] = None
    target_agent: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def model_dump(self) -> dict:
        return {
            "decision_type": self.decision_type.value,
            "reason": self.reason,
            "target_step": self.target_step,
            "target_agent": self.target_agent,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class WorkflowMonitor:
    """
    Monitoring state for an active workflow.
    """
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    step_results: Dict[str, Any] = field(default_factory=dict)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[SupervisorDecision] = field(default_factory=list)
    retry_counts: Dict[str, int] = field(default_factory=dict)
    
    def model_dump(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "step_results": self.step_results,
            "failures": self.failures,
            "decisions": [d.model_dump() for d in self.decisions],
            "retry_counts": self.retry_counts,
        }


@dataclass
class DailyLog:
    """
    Human-readable daily activity log.
    """
    date: str
    workflows_started: int = 0
    workflows_completed: int = 0
    workflows_failed: int = 0
    total_retries: int = 0
    escalations: int = 0
    entries: List[str] = field(default_factory=list)
    
    def add_entry(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.entries.append(f"[{timestamp}] {message}")
    
    def model_dump(self) -> dict:
        return {
            "date": self.date,
            "workflows_started": self.workflows_started,
            "workflows_completed": self.workflows_completed,
            "workflows_failed": self.workflows_failed,
            "total_retries": self.total_retries,
            "escalations": self.escalations,
            "entries": self.entries,
        }
    
    def to_text(self) -> str:
        """Generate human-readable log text."""
        lines = [
            f"=== Supervisor Daily Log: {self.date} ===",
            "",
            "Summary:",
            f"  Workflows Started:   {self.workflows_started}",
            f"  Workflows Completed: {self.workflows_completed}",
            f"  Workflows Failed:    {self.workflows_failed}",
            f"  Total Retries:       {self.total_retries}",
            f"  Escalations:         {self.escalations}",
            "",
            "Activity Log:",
        ]
        lines.extend(f"  {entry}" for entry in self.entries)
        return "\n".join(lines)


# =============================================================================
# SUPERVISOR AGENT
# =============================================================================


class SupervisorAgent:
    """
    Supervisor Agent - Manages and monitors all workflows and agents.
    
    Capabilities:
    - detect_workflow_failure: Identify failed steps
    - decide_recovery_action: Choose retry/skip/escalate
    - retry_step: Attempt to re-run a failed step
    - reassign_task: Move task to a different agent
    - summarize_outcome: Generate human-readable summary
    - enforce_safety: Check safety rules
    - generate_daily_log: Produce activity report
    
    Tools:
    - get_workflow_status(workflow_id)
    - get_step_details(workflow_id, step_name)
    - retry_workflow_step(workflow_id, step_name)
    - escalate_to_human(workflow_id, reason)
    - send_agent_message(recipient, message)
    """
    
    SYSTEM_PROMPT = """You are the Supervisor Agent for an accounting automation system.
Your role is to:
1. Monitor all active workflows for failures or anomalies
2. Decide whether to retry, escalate, or skip failed steps
3. Ensure safety rules are maintained (no direct money movement)
4. Summarize workflow outcomes for human review
5. Coordinate between specialized agents when needed

Always prioritize:
- Data integrity over speed
- Clear audit trails over automation
- Human escalation for high-risk decisions

Safety Rules:
- Never directly modify financial records without human approval
- Flag any transaction > $10,000 for review
- Escalate unbalanced journal entries immediately
- Log all decisions for audit purposes
"""
    
    def __init__(self, max_retries: int = 3):
        self._monitors: Dict[str, WorkflowMonitor] = {}
        self._max_retries = max_retries
        self._daily_log = DailyLog(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        self._safety_rules: List[Callable] = []
        self._tools: Dict[str, Callable] = {}
        
        # Register default tools
        self._register_default_tools()
        
        # Subscribe to messages
        self._setup_messaging()
    
    # =========================================================================
    # MONITORING
    # =========================================================================
    
    def start_monitoring(self, workflow_id: str, workflow_name: str) -> WorkflowMonitor:
        """Start monitoring a workflow."""
        monitor = WorkflowMonitor(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self._monitors[workflow_id] = monitor
        self._daily_log.workflows_started += 1
        self._daily_log.add_entry(f"Started workflow: {workflow_name} ({workflow_id})")
        
        logger.info(f"Supervisor: Started monitoring {workflow_name}")
        return monitor
    
    def get_monitor(self, workflow_id: str) -> Optional[WorkflowMonitor]:
        """Get monitoring state for a workflow."""
        return self._monitors.get(workflow_id)
    
    def report_step_result(
        self,
        workflow_id: str,
        step_name: str,
        status: str,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Report a step result (called by workflow engine)."""
        monitor = self._monitors.get(workflow_id)
        if not monitor:
            return
        
        monitor.step_results[step_name] = {
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        }
        
        if status == "failed" and error:
            monitor.failures.append({
                "step": step_name,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._handle_failure(workflow_id, step_name, error)
    
    def report_workflow_complete(
        self,
        workflow_id: str,
        status: str,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Report workflow completion."""
        monitor = self._monitors.get(workflow_id)
        if not monitor:
            return
        
        monitor.completed_at = datetime.now(timezone.utc)
        
        if status == "success":
            monitor.status = WorkflowStatus.SUCCESS
            self._daily_log.workflows_completed += 1
            self._daily_log.add_entry(f"Completed: {monitor.workflow_name} ✓")
        elif status == "partial":
            monitor.status = WorkflowStatus.PARTIAL
            self._daily_log.workflows_completed += 1
            self._daily_log.add_entry(f"Partial completion: {monitor.workflow_name}")
        else:
            monitor.status = WorkflowStatus.FAILED
            self._daily_log.workflows_failed += 1
            self._daily_log.add_entry(f"Failed: {monitor.workflow_name} ✗")
        
        logger.info(f"Supervisor: Workflow {workflow_id} completed with status: {status}")
    
    # =========================================================================
    # FAILURE HANDLING
    # =========================================================================
    
    def _handle_failure(
        self,
        workflow_id: str,
        step_name: str,
        error: str,
    ) -> SupervisorDecision:
        """Handle a step failure and decide recovery action."""
        monitor = self._monitors.get(workflow_id)
        if not monitor:
            return SupervisorDecision(
                decision_type=DecisionType.ABORT,
                reason="Workflow not found",
            )
        
        # Track retries
        retry_count = monitor.retry_counts.get(step_name, 0)
        
        # Decide action
        decision = self._decide_recovery(step_name, error, retry_count)
        monitor.decisions.append(decision)
        
        # Execute decision
        if decision.decision_type == DecisionType.RETRY:
            if retry_count < self._max_retries:
                monitor.retry_counts[step_name] = retry_count + 1
                monitor.status = WorkflowStatus.RETRYING
                self._daily_log.total_retries += 1
                self._daily_log.add_entry(f"Retrying step: {step_name} (attempt {retry_count + 1})")
            else:
                decision = SupervisorDecision(
                    decision_type=DecisionType.ESCALATE,
                    reason=f"Max retries exceeded for {step_name}",
                    target_step=step_name,
                )
                self._escalate(workflow_id, decision)
        
        elif decision.decision_type == DecisionType.ESCALATE:
            self._escalate(workflow_id, decision)
        
        elif decision.decision_type == DecisionType.REASSIGN:
            self._reassign(workflow_id, decision)
        
        return decision
    
    def _decide_recovery(
        self,
        step_name: str,
        error: str,
        retry_count: int,
    ) -> SupervisorDecision:
        """Decide how to recover from a failure."""
        error_lower = error.lower()
        
        # Critical errors - escalate immediately
        if any(word in error_lower for word in ["unbalanced", "fraud", "security"]):
            return SupervisorDecision(
                decision_type=DecisionType.ESCALATE,
                reason=f"Critical error in {step_name}: {error[:100]}",
                target_step=step_name,
            )
        
        # Transient errors - retry
        if any(word in error_lower for word in ["timeout", "connection", "temporary"]):
            return SupervisorDecision(
                decision_type=DecisionType.RETRY,
                reason="Transient error detected",
                target_step=step_name,
                retry_count=retry_count,
            )
        
        # Data errors - try reassignment
        if any(word in error_lower for word in ["parse", "format", "invalid"]):
            if retry_count == 0:
                return SupervisorDecision(
                    decision_type=DecisionType.RETRY,
                    reason="Data format error - retrying",
                    target_step=step_name,
                )
            else:
                return SupervisorDecision(
                    decision_type=DecisionType.SKIP,
                    reason="Persistent data error - skipping step",
                    target_step=step_name,
                )
        
        # Default - retry then escalate
        if retry_count < self._max_retries:
            return SupervisorDecision(
                decision_type=DecisionType.RETRY,
                reason="Unknown error - attempting retry",
                target_step=step_name,
                retry_count=retry_count,
            )
        
        return SupervisorDecision(
            decision_type=DecisionType.ESCALATE,
            reason="Max retries exceeded",
            target_step=step_name,
        )
    
    def _escalate(self, workflow_id: str, decision: SupervisorDecision) -> None:
        """Escalate an issue to human review."""
        monitor = self._monitors.get(workflow_id)
        if monitor:
            monitor.status = WorkflowStatus.ESCALATED
        
        self._daily_log.escalations += 1
        self._daily_log.add_entry(f"ESCALATED: {decision.reason}")
        
        # Send alert
        alert_agent(
            sender="supervisor",
            recipient="operations",
            subject=f"Escalation: {decision.reason}",
            details={
                "workflow_id": workflow_id,
                "decision": decision.model_dump(),
            },
        )
        
        logger.warning(f"Supervisor: Escalated workflow {workflow_id}: {decision.reason}")
    
    def _reassign(self, workflow_id: str, decision: SupervisorDecision) -> None:
        """Reassign a task to a different agent."""
        self._daily_log.add_entry(
            f"Reassigned: {decision.target_step} → {decision.target_agent}"
        )
        
        # Send task request to new agent
        if decision.target_agent:
            send_message(
                sender="supervisor",
                recipient=decision.target_agent,
                message_type=MessageType.TASK_REQUEST,
                subject=f"Reassigned task: {decision.target_step}",
                payload={
                    "workflow_id": workflow_id,
                    "step": decision.target_step,
                    "original_error": decision.reason,
                },
            )
    
    # =========================================================================
    # SAFETY RULES
    # =========================================================================
    
    def add_safety_rule(self, rule: Callable[[Dict], bool]) -> None:
        """Add a safety rule checker."""
        self._safety_rules.append(rule)
    
    def check_safety(self, context: Dict[str, Any]) -> List[str]:
        """Check all safety rules and return violations."""
        violations = []
        
        for rule in self._safety_rules:
            try:
                if not rule(context):
                    violations.append(f"Safety rule violation: {rule.__name__}")
            except Exception as e:
                violations.append(f"Safety rule error: {e}")
        
        return violations
    
    def enforce_default_safety(self, context: Dict[str, Any]) -> List[str]:
        """Enforce default safety rules."""
        violations = []
        
        # Check for high-value transactions
        journal_entries = context.get("journal_entries", [])
        for entry in journal_entries:
            if hasattr(entry, "total_debits"):
                total = entry.total_debits
            elif isinstance(entry, dict):
                total = entry.get("total_debits", "0")
            else:
                continue
            
            try:
                from decimal import Decimal
                if Decimal(str(total)) > Decimal("10000"):
                    violations.append(f"High-value transaction: ${total}")
            except:
                pass
        
        # Check for unbalanced entries
        for entry in journal_entries:
            is_balanced = False
            if hasattr(entry, "is_balanced"):
                is_balanced = entry.is_balanced
            elif isinstance(entry, dict):
                is_balanced = entry.get("is_balanced", True)
            
            if not is_balanced:
                entry_id = getattr(entry, "entry_id", None) or entry.get("entry_id", "unknown")
                violations.append(f"Unbalanced entry: {entry_id}")
        
        return violations
    
    # =========================================================================
    # SUMMARIZATION
    # =========================================================================
    
    def summarize_workflow(self, workflow_id: str) -> str:
        """Generate a human-readable summary of a workflow."""
        monitor = self._monitors.get(workflow_id)
        if not monitor:
            return f"Workflow {workflow_id} not found."
        
        lines = [
            f"Workflow: {monitor.workflow_name}",
            f"Status: {monitor.status.value}",
            f"Started: {monitor.started_at}",
            f"Completed: {monitor.completed_at}",
            "",
            "Steps:",
        ]
        
        for step, result in monitor.step_results.items():
            status = result.get("status", "unknown")
            duration = result.get("duration_ms", 0)
            symbol = "✓" if status == "success" else "✗"
            lines.append(f"  {symbol} {step}: {status} ({duration:.2f}ms)")
        
        if monitor.failures:
            lines.append("")
            lines.append("Failures:")
            for failure in monitor.failures:
                lines.append(f"  - {failure['step']}: {failure['error'][:50]}")
        
        if monitor.decisions:
            lines.append("")
            lines.append("Decisions:")
            for decision in monitor.decisions:
                lines.append(f"  - {decision.decision_type.value}: {decision.reason}")
        
        return "\n".join(lines)
    
    def get_daily_log(self) -> DailyLog:
        """Get the current daily log."""
        return self._daily_log
    
    def reset_daily_log(self) -> DailyLog:
        """Reset and return the daily log (for new day)."""
        old_log = self._daily_log
        self._daily_log = DailyLog(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        return old_log
    
    # =========================================================================
    # TOOLS
    # =========================================================================
    
    def _register_default_tools(self) -> None:
        """Register default supervisor tools."""
        self._tools["get_workflow_status"] = self._tool_get_status
        self._tools["retry_step"] = self._tool_retry_step
        self._tools["escalate"] = self._tool_escalate
        self._tools["send_message"] = self._tool_send_message
    
    def _tool_get_status(self, workflow_id: str) -> Dict[str, Any]:
        """Tool: Get workflow status."""
        monitor = self._monitors.get(workflow_id)
        if monitor:
            return monitor.model_dump()
        return {"error": "Workflow not found"}
    
    def _tool_retry_step(self, workflow_id: str, step_name: str) -> Dict[str, Any]:
        """Tool: Retry a failed step."""
        monitor = self._monitors.get(workflow_id)
        if not monitor:
            return {"error": "Workflow not found"}
        
        # This would integrate with the workflow engine
        return {
            "status": "retry_scheduled",
            "workflow_id": workflow_id,
            "step": step_name,
        }
    
    def _tool_escalate(self, workflow_id: str, reason: str) -> Dict[str, Any]:
        """Tool: Escalate to human review."""
        decision = SupervisorDecision(
            decision_type=DecisionType.ESCALATE,
            reason=reason,
        )
        self._escalate(workflow_id, decision)
        return {"status": "escalated", "reason": reason}
    
    def _tool_send_message(
        self,
        recipient: str,
        subject: str,
        content: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Tool: Send message to another agent."""
        msg = send_message(
            sender="supervisor",
            recipient=recipient,
            message_type=MessageType.INFO,
            subject=subject,
            payload=content,
        )
        return {"status": "sent", "message_id": msg.id}
    
    # =========================================================================
    # MESSAGING
    # =========================================================================
    
    def _setup_messaging(self) -> None:
        """Set up message bus subscriptions."""
        bus = get_message_bus()
        bus.subscribe("supervisor", "workflow_events", self._handle_message)
        bus.subscribe("supervisor", "alerts", self._handle_message)
        bus.router.register_agent("supervisor", self._handle_message)
    
    def _handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages."""
        if message.type == MessageType.ALERT:
            self._daily_log.add_entry(f"Received alert: {message.subject}")
        elif message.type == MessageType.WORKFLOW_FAILED:
            workflow_id = message.payload.get("workflow_id")
            if workflow_id:
                self.report_workflow_complete(workflow_id, "failed")
