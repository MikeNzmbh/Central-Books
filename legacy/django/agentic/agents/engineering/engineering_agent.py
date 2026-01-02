"""
Engineering Agent - AI Employee for Development Assistance

Handles:
- Error log summarization
- Fix suggestions for stack traces
- Code review assistance
- Documentation generation
"""

from typing import Any, Dict, List, Optional

from agentic_core.agents.base_agent import BaseAgent
from agentic.agents.shared.profile import AgentProfile


class EngineeringAgent(BaseAgent):
    """
    AI Employee for engineering and development assistance.

    Capabilities:
    - Summarize error logs
    - Suggest fixes for stack traces
    - Assist with code review
    - Generate technical documentation

    This agent has MEDIUM risk level as it provides
    technical recommendations that could affect code.
    """

    agent_name = "engineering_agent"
    agent_version = "0.1.0"

    profile = AgentProfile(
        name="Engineering Agent",
        role="engineering",
        description=(
            "AI employee responsible for engineering and development support. "
            "Summarizes error logs, suggests fixes for bugs, assists with code "
            "review, and generates technical documentation."
        ),
        capabilities=[
            "summarize_error_logs",
            "suggest_fix_priors",
            "review_code_changes",
            "generate_documentation",
            "analyze_stack_trace",
            "propose_architecture_improvements",
        ],
        max_parallel_tasks=3,
        risk_level="medium",
        llm_model="deepseek-reasoner",
        system_prompt=(
            "You are a senior Engineering AI assistant. Your role is to help "
            "developers debug issues, improve code quality, and maintain "
            "documentation. Be precise, reference specific code patterns, and "
            "prioritize practical solutions over theoretical purity."
        ),
        tools=[
            "code_search",
            "log_fetcher",
            "git_history",
            "test_runner",
        ],
        owner_team="engineering",
    )

    def __init__(self, llm_client: Optional[Any] = None, **kwargs: Any):
        """Initialize the Engineering Agent."""
        super().__init__(llm_client=llm_client, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Default run method - delegates to specific capability methods."""
        self.log_step("EngineeringAgent.run() called - use specific methods instead")
        return {"status": "use_specific_methods"}

    async def summarize_error_logs(
        self,
        logs: List[str],
    ) -> str:
        """
        Summarize a list of error logs.

        Args:
            logs: List of error log entries.

        Returns:
            Summarized analysis of the errors.
        """
        self.log_step(f"Summarizing {len(logs)} error logs")

        # Build prompt spec
        prompt_spec = {
            "task": "summarize_errors",
            "log_count": len(logs),
            "sample_logs": logs[:3] if logs else [],
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        if not logs:
            return "No error logs to analyze."

        # Analyze error patterns
        error_types: Dict[str, int] = {}
        for log in logs:
            log_lower = log.lower()
            if "timeout" in log_lower:
                error_types["Timeout"] = error_types.get("Timeout", 0) + 1
            elif "connection" in log_lower:
                error_types["Connection"] = error_types.get("Connection", 0) + 1
            elif "null" in log_lower or "undefined" in log_lower or "none" in log_lower:
                error_types["Null Reference"] = error_types.get("Null Reference", 0) + 1
            elif "permission" in log_lower or "denied" in log_lower:
                error_types["Permission"] = error_types.get("Permission", 0) + 1
            elif "syntax" in log_lower or "parse" in log_lower:
                error_types["Syntax/Parse"] = error_types.get("Syntax/Parse", 0) + 1
            elif "memory" in log_lower or "oom" in log_lower:
                error_types["Memory"] = error_types.get("Memory", 0) + 1
            else:
                error_types["Other"] = error_types.get("Other", 0) + 1

        # Build summary
        summary_parts = [f"**Error Log Analysis** ({len(logs)} entries)\n"]

        if error_types:
            summary_parts.append("**Error Distribution:**")
            for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
                pct = (count / len(logs)) * 100
                summary_parts.append(f"- {error_type}: {count} ({pct:.1f}%)")

        # Top priority
        if error_types:
            top_error = max(error_types.items(), key=lambda x: x[1])[0]
            summary_parts.append(f"\n**Priority:** Focus on {top_error} errors first.")

        return "\n".join(summary_parts)

    async def suggest_fix_priors(
        self,
        stack_trace: str,
        module_hint: str,
    ) -> List[str]:
        """
        Suggest fix priorities based on a stack trace.

        Args:
            stack_trace: The error stack trace.
            module_hint: Hint about which module is affected.

        Returns:
            Ordered list of suggested fixes to try.
        """
        self.log_step(f"Analyzing stack trace for module: {module_hint}")

        # Build prompt spec
        prompt_spec = {
            "task": "suggest_fixes",
            "stack_trace_length": len(stack_trace),
            "module": module_hint,
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        suggestions: List[str] = []
        trace_lower = stack_trace.lower()

        # Pattern-based suggestions
        if "keyerror" in trace_lower or "key" in trace_lower:
            suggestions.append("1. Check for missing dictionary keys - add .get() with default")
            suggestions.append("2. Verify input data structure matches expected schema")

        if "typeerror" in trace_lower:
            suggestions.append("1. Check argument types being passed to functions")
            suggestions.append("2. Verify None checks before method calls")

        if "attributeerror" in trace_lower:
            suggestions.append("1. Check if object is None before accessing attributes")
            suggestions.append("2. Verify import statements are correct")

        if "importerror" in trace_lower or "modulenotfound" in trace_lower:
            suggestions.append("1. Check requirements.txt/pyproject.toml for missing dependency")
            suggestions.append("2. Verify virtual environment is activated")
            suggestions.append("3. Check for circular import issues")

        if "connectionerror" in trace_lower or "timeout" in trace_lower:
            suggestions.append("1. Check network connectivity and firewall rules")
            suggestions.append("2. Increase timeout values in configuration")
            suggestions.append("3. Add retry logic with exponential backoff")

        if "integrityerror" in trace_lower or "duplicate" in trace_lower:
            suggestions.append("1. Check for duplicate key violations")
            suggestions.append("2. Add unique constraint handling or upsert logic")

        # Module-specific suggestions
        if "bank" in module_hint.lower() or "plaid" in module_hint.lower():
            suggestions.append("Check Plaid API credentials and webhook configuration")
        elif "invoice" in module_hint.lower():
            suggestions.append("Verify invoice line item calculations and tax handling")
        elif "report" in module_hint.lower():
            suggestions.append("Check date range filters and aggregation logic")

        if not suggestions:
            suggestions = [
                "1. Review the full stack trace for the root cause",
                "2. Add logging to narrow down the issue",
                "3. Check recent code changes in the affected module",
                "4. Search codebase for similar patterns",
            ]

        return suggestions

    async def analyze_dependencies(
        self,
        module_name: str,
        import_errors: List[str],
    ) -> Dict[str, Any]:
        """
        Analyze dependency issues for a module.

        Args:
            module_name: Name of the module with issues.
            import_errors: List of import error messages.

        Returns:
            Analysis with recommendations.
        """
        self.log_step(f"Analyzing dependencies for: {module_name}")

        missing_packages = []
        circular_imports = []
        version_conflicts = []

        for error in import_errors:
            error_lower = error.lower()
            if "no module named" in error_lower:
                # Extract package name
                parts = error.split("'")
                if len(parts) >= 2:
                    missing_packages.append(parts[1])
            elif "circular" in error_lower:
                circular_imports.append(error)
            elif "version" in error_lower or "incompatible" in error_lower:
                version_conflicts.append(error)

        recommendations = []
        if missing_packages:
            recommendations.append(f"Install missing packages: pip install {' '.join(missing_packages)}")
        if circular_imports:
            recommendations.append("Refactor to break circular dependencies (use lazy imports)")
        if version_conflicts:
            recommendations.append("Review requirements.txt and pin compatible versions")

        return {
            "module": module_name,
            "missing_packages": missing_packages,
            "circular_imports": circular_imports,
            "version_conflicts": version_conflicts,
            "recommendations": recommendations,
        }
