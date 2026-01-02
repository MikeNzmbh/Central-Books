"""
Centralized tone configuration for AI Companion.

This module provides tone mapping based on risk level, time-of-day greetings,
and user name personalization for all DeepSeek outputs.

Usage:
    from core.llm_tone import build_companion_preamble
    
    preamble = build_companion_preamble(
        user_name="Mike",
        risk_level="medium",
        surface="books",
    )
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

# ---------------------------------------------------------------------------
# RISK LEVEL → TONE MAPPING
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "medium", "high", "critical"]
Surface = Literal["receipts", "invoices", "books", "bank", "issues"]

RISK_TONE_MAP: dict[str, dict[str, str]] = {
    "low": {
        "tone": "friendly, warm, reassuring",
        "greeting_style": "casual",  # "Good morning Mike," or "Hey Mike,"
        "instruction": (
            "Use a friendly, warm, and reassuring tone. The user's data looks healthy. "
            "Be positive and encouraging. You can use casual greetings like 'Hey {name},' or 'Good {time} {name},'. "
            "Suggest they skim things when convenient, but there's no urgency. Keep it light and supportive."
        ),
        "example": (
            "Good morning Mike, your receipts for Friday look well managed. Everything processed cleanly "
            "with no high-risk flags. If you have a minute later, just skim the Receipts workspace to confirm "
            "the categories look right."
        ),
    },
    "medium": {
        "tone": "calm, gently nudging, helpful",
        "greeting_style": "warm",  # "Hi Mike,"
        "instruction": (
            "Use a calm, helpful tone with a gentle nudge. Things are mostly fine but a few items need attention. "
            "Use warm greetings like 'Hi {name},'. Be specific about what needs review and suggest where to start. "
            "Don't alarm the user, but make it clear there's some follow-up needed when they have time."
        ),
        "example": (
            "Hi Mike, your Scotia checking account is mostly in good shape, but I found a few items worth a closer look. "
            "There are 9 unmatched transactions and 2 possible duplicates. When you have a moment, start in the "
            "'Unmatched' tab and clear those first."
        ),
    },
    "high": {
        "tone": "clear, firm, supportive",
        "greeting_style": "professional",  # "Hi Mike," or "Good {time} Mike,"
        "instruction": (
            "Use a clear, firm, but still supportive tone. There are real issues that need attention soon. "
            "Use professional greetings like 'Hi {name},' or 'Good {time} {name},'. Be specific about the most urgent items. "
            "Prioritize what to fix first. Be direct but not alarming—stay calm and helpful."
        ),
        "example": (
            "Hi Mike, your books for last week show a few high-risk issues that need attention soon. "
            "The most urgent is a negative balance in your GST/HST Payable account, plus a $1,200 suspense balance "
            "and one unbalanced journal. Let's fix those first so your statements become reliable again."
        ),
    },
    "critical": {
        "tone": "very direct, calm, clearly urgent",
        "greeting_style": "professional",  # "Good {time} Mike,"
        "instruction": (
            "Use a very direct but calm tone. There are critical issues that need immediate attention. "
            "Use professional greetings like 'Good {time} {name},'. Clearly state the problems and recommend "
            "a prioritized order to address them. Be urgent but not panicked—stay grounded and actionable."
        ),
        "example": (
            "Good morning Mike, there are several critical accounting issues we should address as soon as you can: "
            "overdue invoices, unreconciled bank transactions, and a large suspense balance. I recommend reconciling "
            "the bank transactions first, then clearing suspense, then following up on the overdue invoices."
        ),
    },
}

SURFACE_CONTEXT: dict[str, str] = {
    "receipts": "expense receipts and their classification",
    "invoices": "sales invoices and accounts receivable",
    "books": "general ledger health and journal entries",
    "bank": "bank transactions and reconciliation status",
    "issues": "overall financial health and open issues",
}


def get_time_of_day() -> str:
    """
    Returns 'morning', 'afternoon', or 'evening' based on current server time.
    
    - Morning: 5:00 - 11:59
    - Afternoon: 12:00 - 16:59
    - Evening: 17:00 - 4:59
    """
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    else:
        return "evening"


def get_greeting(user_name: str | None, risk_level: str = "medium", time_of_day: str | None = None) -> str:
    """
    Returns a personalized greeting based on user name and risk level.
    
    Low risk: casual ("Hey Mike," or "Good morning Mike,")
    Medium risk: warm ("Hi Mike,")
    High/Critical risk: professional ("Good morning Mike," or "Hi Mike,")
    
    Fallback when no name: "Good morning," or "Hi there,"
    """
    tod = time_of_day or get_time_of_day()
    risk_key = risk_level.lower() if risk_level else "medium"
    
    if user_name and user_name.strip():
        name = user_name.strip().split()[0]  # Use first name only
        
        if risk_key == "low":
            # Casual for low risk
            return f"Good {tod} {name},"
        elif risk_key == "medium":
            # Warm for medium
            return f"Hi {name},"
        else:
            # Professional for high/critical
            return f"Good {tod} {name},"
    else:
        # Fallback without name
        if risk_key in ("low", "medium"):
            return f"Hi there,"
        else:
            return f"Good {tod},"


def build_companion_preamble(
    user_name: str | None = None,
    risk_level: str = "medium",
    surface: str = "issues",
) -> str:
    """
    Builds the system prompt preamble for DeepSeek with friendly tone, name, and context.
    
    Args:
        user_name: The user's first name (from request.user.first_name), or None.
        risk_level: One of "low", "medium", "high", "critical".
        surface: The context surface (receipts, invoices, books, bank, issues).
    
    Returns:
        A system prompt preamble string to prepend to LLM prompts.
    """
    # Normalize risk level
    risk_key = risk_level.lower() if risk_level else "medium"
    if risk_key not in RISK_TONE_MAP:
        risk_key = "medium"
    
    tone_config = RISK_TONE_MAP[risk_key]
    tone_instruction = tone_config["instruction"]
    tone_example = tone_config["example"]
    
    # Get greeting and name
    tod = get_time_of_day()
    greeting = get_greeting(user_name, risk_key, tod)
    name_part = user_name.strip().split()[0] if user_name and user_name.strip() else "the user"
    
    # Get surface context
    surface_key = surface.lower() if surface else "issues"
    surface_desc = SURFACE_CONTEXT.get(surface_key, "financial health")
    
    preamble = f"""You are an AI accounting companion for a small business owner named {name_part}.

GREETING & TONE:
- Always start your response with a greeting: "{greeting}"
- {tone_instruction}
- Keep responses short: 1-3 paragraphs maximum.
- Be warm, personal, and human. Sound like a helpful colleague, not a robot.
- Never invent the user's name. Only use "{name_part}" if that's what was provided.

EXAMPLE OF THE RIGHT TONE:
"{tone_example}"

SAFETY RULES (never break these):
- Never say you took action (e.g., "I fixed," "I reconciled," "I posted").
- Only describe what you observe and suggest what {name_part} can review or do next.
- All suggestions are proposals only; {name_part} decides what to do.
- Never invent transactions, amounts, dates, or account codes not in the data.

CONTEXT:
You are analyzing {surface_desc}. The current risk level is: {risk_key}.
The current time of day is: {tod}.
"""
    return preamble


def determine_risk_level(
    high_risk_count: int = 0,
    critical_count: int = 0,
    unreconciled_count: int = 0,
    compliance_flag: bool = False,
) -> RiskLevel:
    """
    Heuristic to determine overall risk level from metrics.
    
    Returns:
        One of "low", "medium", "high", "critical".
    """
    if critical_count > 0 or compliance_flag:
        return "critical"
    if high_risk_count >= 5 or unreconciled_count >= 10:
        return "high"
    if high_risk_count > 0 or unreconciled_count > 0:
        return "medium"
    return "low"
