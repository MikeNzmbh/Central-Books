"""
Support Agent - AI Employee for Customer Support

Handles:
- Answering user questions using knowledge base
- Suggesting onboarding steps for new businesses
- Ticket triage and routing
- Help documentation generation
"""

from typing import Any, Dict, List, Optional

from agentic_core.agents.base_agent import BaseAgent
from agentic.agents.shared.profile import AgentProfile


class SupportAgent(BaseAgent):
    """
    AI Employee for customer support and help desk automation.

    Capabilities:
    - Answer user questions with context
    - Suggest onboarding steps
    - Triage support tickets
    - Generate help documentation

    This agent has LOW risk level as it primarily
    provides information without modifying data.
    """

    agent_name = "support_agent"
    agent_version = "0.1.0"

    profile = AgentProfile(
        name="Support Agent",
        role="support",
        description=(
            "AI employee responsible for customer support and help desk automation. "
            "Answers user questions, suggests onboarding steps, triages tickets, "
            "and generates contextual help documentation."
        ),
        capabilities=[
            "answer_user_question",
            "suggest_onboarding_steps",
            "triage_support_ticket",
            "generate_help_article",
            "explain_feature",
            "troubleshoot_issue",
        ],
        max_parallel_tasks=10,
        risk_level="low",
        llm_model="gpt-4.1-mini",
        system_prompt=(
            "You are a friendly and knowledgeable Support AI assistant. Your role is "
            "to help users understand the product, troubleshoot issues, and provide "
            "clear guidance. Be patient, empathetic, and thorough in your explanations."
        ),
        tools=[
            "knowledge_base_search",
            "ticket_creator",
            "user_context_loader",
        ],
        owner_team="customer_success",
    )

    def __init__(self, llm_client: Optional[Any] = None, **kwargs: Any):
        """Initialize the Support Agent."""
        super().__init__(llm_client=llm_client, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Default run method - delegates to specific capability methods."""
        self.log_step("SupportAgent.run() called - use specific methods instead")
        return {"status": "use_specific_methods"}

    async def answer_user_question(
        self,
        question: str,
        context_summary: str,
    ) -> str:
        """
        Answer a user's question with context.

        Args:
            question: The user's question.
            context_summary: Summary of relevant context (user info, history, etc.)

        Returns:
            Answer to the user's question.
        """
        self.log_step(f"Answering question: {question[:50]}...")

        # Build prompt spec
        prompt_spec = {
            "task": "answer_question",
            "question": question,
            "context_length": len(context_summary),
            "has_context": bool(context_summary),
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        # Deterministic mock responses based on question keywords
        question_lower = question.lower()

        if "invoice" in question_lower:
            return (
                "To create an invoice, go to Sales > Invoices and click 'New Invoice'. "
                "Fill in the customer details, add line items, and click 'Save'. "
                "You can then send it directly via email or download as PDF."
            )
        elif "reconcil" in question_lower:
            return (
                "Bank reconciliation matches your bank transactions with your ledger. "
                "Go to Banking > Reconciliation, select your account, and review "
                "the imported transactions. Match or categorize each one."
            )
        elif "report" in question_lower:
            return (
                "You can access financial reports from Reports in the sidebar. "
                "Available reports include Profit & Loss, Cash Flow, and Balance Sheet. "
                "Select a date range and click 'Generate'."
            )
        elif "password" in question_lower or "login" in question_lower:
            return (
                "To reset your password, click 'Forgot Password' on the login page. "
                "Enter your email and we'll send you a reset link. "
                "If you're still having trouble, contact support@cernbooks.com."
            )
        else:
            return (
                f"Thank you for your question about '{question[:30]}...'. "
                "I'd be happy to help. Could you provide more details about what "
                "you're trying to accomplish? You can also check our Help Center at "
                "help.cernbooks.com for guides and tutorials."
            )

    async def suggest_onboarding_steps(
        self,
        business_profile: Dict[str, Any],
    ) -> List[str]:
        """
        Suggest onboarding steps for a new business.

        Args:
            business_profile: Dict with business info (type, size, features, etc.)

        Returns:
            Ordered list of recommended onboarding steps.
        """
        self.log_step(f"Generating onboarding steps for: {business_profile.get('name', 'Unknown')}")

        # Build prompt spec
        prompt_spec = {
            "task": "suggest_onboarding",
            "business_type": business_profile.get("type", "general"),
            "business_size": business_profile.get("size", "small"),
            "features": business_profile.get("features", []),
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        # Base onboarding steps
        steps = [
            "1. Complete your business profile with logo and contact info",
            "2. Connect your bank accounts for automatic transaction import",
            "3. Set up your Chart of Accounts (or use the default template)",
            "4. Add your first customer and create a test invoice",
        ]

        # Add role-specific steps based on business type
        biz_type = business_profile.get("type", "").lower()

        if "ecommerce" in biz_type or "retail" in biz_type:
            steps.append("5. Configure inventory tracking and cost of goods sold")
            steps.append("6. Set up sales tax rates for your jurisdictions")
        elif "service" in biz_type or "consulting" in biz_type:
            steps.append("5. Create service items and hourly rate templates")
            steps.append("6. Set up time tracking for billable hours")
        elif "saas" in biz_type or "software" in biz_type:
            steps.append("5. Configure recurring invoice templates")
            steps.append("6. Set up revenue recognition rules")
        else:
            steps.append("5. Add your suppliers for expense tracking")
            steps.append("6. Review and customize expense categories")

        steps.append("7. Schedule your first bank reconciliation")
        steps.append("8. Explore the Reports section for financial insights")

        return steps

    async def triage_support_ticket(
        self,
        ticket: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Triage a support ticket and suggest routing.

        Args:
            ticket: Dict with subject, description, user_tier, etc.

        Returns:
            Triage result with priority, category, and routing.
        """
        self.log_step(f"Triaging ticket: {ticket.get('subject', 'No subject')[:50]}")

        subject = ticket.get("subject", "").lower()
        description = ticket.get("description", "").lower()
        user_tier = ticket.get("user_tier", "free")
        combined = f"{subject} {description}"

        # Determine priority
        if any(word in combined for word in ["urgent", "critical", "broken", "cant login", "data loss"]):
            priority = "high"
        elif any(word in combined for word in ["bug", "error", "not working", "issue"]):
            priority = "medium"
        else:
            priority = "low"

        # Upgrade priority for premium users
        if user_tier in ["premium", "enterprise"] and priority == "low":
            priority = "medium"

        # Determine category
        if any(word in combined for word in ["invoice", "billing", "payment", "subscription"]):
            category = "billing"
            team = "billing_support"
        elif any(word in combined for word in ["bank", "reconcil", "transaction", "import"]):
            category = "banking"
            team = "banking_support"
        elif any(word in combined for word in ["report", "dashboard", "chart"]):
            category = "reporting"
            team = "general_support"
        elif any(word in combined for word in ["login", "password", "account", "sso"]):
            category = "authentication"
            team = "security_support"
        else:
            category = "general"
            team = "general_support"

        return {
            "priority": priority,
            "category": category,
            "suggested_team": team,
            "auto_response_eligible": priority == "low" and category in ["general", "reporting"],
            "estimated_response_time": "1 hour" if priority == "high" else "4 hours",
        }
