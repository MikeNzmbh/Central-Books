"""
Sales Agent - AI Employee for Sales Assistance

Handles:
- Demo script generation
- Pricing tier proposals
- Lead qualification
- Sales materials generation
"""

from typing import Any, Dict, List, Optional

from agentic_core.agents.base_agent import BaseAgent
from agentic.agents.shared.profile import AgentProfile


class SalesAgent(BaseAgent):
    """
    AI Employee for sales assistance and revenue optimization.

    Capabilities:
    - Generate demo scripts
    - Propose pricing tiers
    - Qualify leads
    - Create sales materials

    This agent has LOW risk level as it generates
    suggestions without direct customer interaction.
    """

    agent_name = "sales_agent"
    agent_version = "0.1.0"

    profile = AgentProfile(
        name="Sales Agent",
        role="sales",
        description=(
            "AI employee responsible for sales assistance and revenue optimization. "
            "Generates demo scripts, proposes pricing strategies, qualifies leads, "
            "and creates targeted sales materials."
        ),
        capabilities=[
            "generate_demo_script",
            "propose_pricing_tiers",
            "qualify_lead",
            "create_pitch_deck_outline",
            "analyze_competitor_positioning",
            "suggest_upsell_opportunities",
        ],
        max_parallel_tasks=5,
        risk_level="low",
        llm_model="gpt-4.1-mini",
        system_prompt=(
            "You are a strategic Sales AI assistant. Your role is to help the sales "
            "team close deals by generating compelling demos, optimizing pricing, and "
            "identifying opportunities. Be persuasive but honest, and focus on "
            "customer value."
        ),
        tools=[
            "crm_lookup",
            "competitor_analyzer",
            "pricing_calculator",
        ],
        owner_team="revenue",
    )

    def __init__(self, llm_client: Optional[Any] = None, **kwargs: Any):
        """Initialize the Sales Agent."""
        super().__init__(llm_client=llm_client, **kwargs)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Default run method - delegates to specific capability methods."""
        self.log_step("SalesAgent.run() called - use specific methods instead")
        return {"status": "use_specific_methods"}

    async def generate_demo_script(
        self,
        feature_flags: Dict[str, Any],
    ) -> str:
        """
        Generate a demo script based on feature flags.

        Args:
            feature_flags: Dict of features to highlight or skip.

        Returns:
            Demo script text with talking points.
        """
        self.log_step(f"Generating demo script for features: {list(feature_flags.keys())}")

        # Build prompt spec
        prompt_spec = {
            "task": "generate_demo_script",
            "features": feature_flags,
            "feature_count": len(feature_flags),
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        # Build script sections based on enabled features
        sections = ["## Clover Books Demo Script\n"]
        sections.append("### Opening (2 min)")
        sections.append("- Welcome and quick company overview")
        sections.append("- Ask about their current pain points\n")

        sections.append("### Core Features (10 min)")

        if feature_flags.get("invoicing", True):
            sections.append("**Invoicing:**")
            sections.append("- Show invoice creation flow")
            sections.append("- Highlight one-click PDF generation")
            sections.append("- Demo recurring invoice setup\n")

        if feature_flags.get("banking", True):
            sections.append("**Bank Connections:**")
            sections.append("- Demo bank account connection via Plaid")
            sections.append("- Show automatic transaction import")
            sections.append("- Highlight smart categorization\n")

        if feature_flags.get("reconciliation", True):
            sections.append("**Reconciliation:**")
            sections.append("- Walk through reconciliation workflow")
            sections.append("- Show AI-powered matching suggestions")
            sections.append("- Highlight bulk actions\n")

        if feature_flags.get("reports", True):
            sections.append("**Reporting:**")
            sections.append("- Show P&L Report with KPIs")
            sections.append("- Demo Cash Flow analysis")
            sections.append("- Highlight export options\n")

        if feature_flags.get("ai_features", False):
            sections.append("**AI Features (Preview):**")
            sections.append("- Show AI transaction categorization")
            sections.append("- Demo receipt scanning")
            sections.append("- Highlight predictive insights\n")

        sections.append("### Pricing & Next Steps (3 min)")
        sections.append("- Present pricing options")
        sections.append("- Offer free trial")
        sections.append("- Schedule follow-up call")

        return "\n".join(sections)

    async def propose_pricing_tiers(
        self,
        target_audience: str,
    ) -> List[Dict[str, Any]]:
        """
        Propose pricing tiers for a target audience.

        Args:
            target_audience: Description of the target market segment.

        Returns:
            List of pricing tier proposals.
        """
        self.log_step(f"Proposing pricing for audience: {target_audience}")

        # Build prompt spec
        prompt_spec = {
            "task": "propose_pricing",
            "audience": target_audience,
        }

        self.log_step(f"Built prompt spec: {prompt_spec}")

        audience_lower = target_audience.lower()

        # Generate pricing based on audience type
        if "enterprise" in audience_lower or "large" in audience_lower:
            tiers = [
                {
                    "name": "Business",
                    "price_monthly": 99,
                    "price_annual": 948,
                    "features": ["Unlimited invoices", "5 bank connections", "Standard reports", "Email support"],
                    "target": "Growing businesses",
                },
                {
                    "name": "Professional",
                    "price_monthly": 249,
                    "price_annual": 2388,
                    "features": ["Everything in Business", "20 bank connections", "Advanced reports", "Priority support", "API access"],
                    "target": "Established companies",
                },
                {
                    "name": "Enterprise",
                    "price_monthly": "Custom",
                    "price_annual": "Custom",
                    "features": ["Everything in Professional", "Unlimited connections", "Custom integrations", "Dedicated CSM", "SLA guarantee"],
                    "target": "Large organizations",
                },
            ]
        elif "startup" in audience_lower or "small" in audience_lower:
            tiers = [
                {
                    "name": "Starter",
                    "price_monthly": 0,
                    "price_annual": 0,
                    "features": ["5 invoices/month", "1 bank connection", "Basic reports"],
                    "target": "Solo founders",
                },
                {
                    "name": "Growth",
                    "price_monthly": 29,
                    "price_annual": 278,
                    "features": ["Unlimited invoices", "3 bank connections", "Standard reports", "Email support"],
                    "target": "Early-stage startups",
                },
                {
                    "name": "Scale",
                    "price_monthly": 79,
                    "price_annual": 758,
                    "features": ["Everything in Growth", "10 bank connections", "Advanced reports", "Priority support"],
                    "target": "Scaling startups",
                },
            ]
        else:
            # Default SMB pricing
            tiers = [
                {
                    "name": "Free",
                    "price_monthly": 0,
                    "price_annual": 0,
                    "features": ["10 invoices/month", "1 bank connection", "Basic P&L report"],
                    "target": "Trying out the product",
                },
                {
                    "name": "Pro",
                    "price_monthly": 49,
                    "price_annual": 470,
                    "features": ["Unlimited invoices", "5 bank connections", "All reports", "Email support"],
                    "target": "Small businesses",
                },
                {
                    "name": "Team",
                    "price_monthly": 99,
                    "price_annual": 950,
                    "features": ["Everything in Pro", "Multi-user", "15 bank connections", "Priority support"],
                    "target": "Growing teams",
                },
            ]

        return tiers

    async def qualify_lead(
        self,
        lead_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Qualify a sales lead and provide scoring.

        Args:
            lead_info: Dict with company, size, industry, needs, etc.

        Returns:
            Lead qualification result with score and recommendations.
        """
        self.log_step(f"Qualifying lead: {lead_info.get('company', 'Unknown')}")

        score = 0
        signals = []

        # Company size scoring
        size = lead_info.get("size", "").lower()
        if "enterprise" in size or lead_info.get("employees", 0) > 500:
            score += 30
            signals.append("Enterprise-sized company (high value)")
        elif "medium" in size or lead_info.get("employees", 0) > 50:
            score += 20
            signals.append("Mid-market company (good fit)")
        elif "small" in size or lead_info.get("employees", 0) > 5:
            score += 10
            signals.append("Small business (standard deal)")

        # Industry fit
        industry = lead_info.get("industry", "").lower()
        high_fit_industries = ["saas", "ecommerce", "consulting", "agency", "professional services"]
        if any(ind in industry for ind in high_fit_industries):
            score += 25
            signals.append(f"High-fit industry: {industry}")

        # Intent signals
        if lead_info.get("requested_demo"):
            score += 20
            signals.append("Requested demo (high intent)")
        if lead_info.get("visited_pricing"):
            score += 15
            signals.append("Visited pricing page")
        if lead_info.get("current_solution"):
            score += 10
            signals.append("Has existing solution (switching)")

        # Determine qualification
        if score >= 60:
            qualification = "hot"
            action = "Schedule demo within 24 hours"
        elif score >= 40:
            qualification = "warm"
            action = "Send personalized email sequence"
        else:
            qualification = "cold"
            action = "Add to nurture campaign"

        return {
            "score": min(score, 100),
            "qualification": qualification,
            "signals": signals,
            "recommended_action": action,
            "suggested_tier": "Enterprise" if score >= 70 else "Pro",
        }
