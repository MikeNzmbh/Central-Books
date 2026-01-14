use std::env;

#[derive(Debug, Clone)]
pub struct PolicyConfig {
    pub approval_amount_threshold: f64,
    pub velocity_threshold: i64,
    pub snapshot_stale_minutes: i64,
}

#[derive(Debug, Clone)]
pub struct BudgetConfig {
    pub tokens_per_day: i64,
    pub tool_calls_per_day: i64,
    pub runs_per_day: i64,
}

#[derive(Debug, Clone, Copy)]
pub enum EngineMode {
    AutopilotLimited,
    Drafts,
    SuggestOnly,
}

impl EngineMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            EngineMode::AutopilotLimited => "autopilot_limited",
            EngineMode::Drafts => "drafts",
            EngineMode::SuggestOnly => "suggest_only",
        }
    }
}

impl PolicyConfig {
    pub fn from_env() -> Self {
        let approval_amount_threshold = env::var("ENGINE_APPROVAL_AMOUNT_THRESHOLD")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(1000.0);
        let velocity_threshold = env::var("ENGINE_VELOCITY_THRESHOLD")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(50);
        let snapshot_stale_minutes = env::var("ENGINE_SNAPSHOT_STALE_MINUTES")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(15);
        Self {
            approval_amount_threshold,
            velocity_threshold,
            snapshot_stale_minutes,
        }
    }
}

impl BudgetConfig {
    pub fn from_env() -> Self {
        let tokens_per_day = env::var("ENGINE_BUDGET_TOKENS_PER_DAY")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(100_000);
        let tool_calls_per_day = env::var("ENGINE_BUDGET_TOOL_CALLS_PER_DAY")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(500);
        let runs_per_day = env::var("ENGINE_BUDGET_RUNS_PER_DAY")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(200);
        Self {
            tokens_per_day,
            tool_calls_per_day,
            runs_per_day,
        }
    }
}

pub fn requires_approval(amount: Option<f64>, config: &PolicyConfig) -> bool {
    amount
        .map(|value| value >= config.approval_amount_threshold)
        .unwrap_or(false)
}

pub fn confidence_for_amount(amount: Option<f64>) -> f64 {
    match amount {
        Some(value) if value >= 5000.0 => 0.55,
        Some(value) if value >= 1000.0 => 0.65,
        Some(value) if value >= 250.0 => 0.75,
        Some(_) => 0.85,
        None => 0.7,
    }
}

pub fn risk_for_amount(amount: Option<f64>) -> &'static str {
    match amount {
        Some(value) if value >= 5000.0 => "high",
        Some(value) if value >= 1000.0 => "medium",
        Some(_) => "low",
        None => "medium",
    }
}

pub fn trust_score(accepted: i64, dismissed: i64, breaker_events: i64) -> f64 {
    let total = accepted + dismissed;
    let base = if total <= 0 {
        75.0
    } else {
        (accepted as f64 / total as f64) * 100.0
    };
    let penalty = (breaker_events as f64) * 7.5;
    (base - penalty).clamp(0.0, 100.0)
}

pub fn derive_engine_mode(trust_score: f64, breaker_recent: bool) -> EngineMode {
    if breaker_recent || trust_score < 50.0 {
        EngineMode::SuggestOnly
    } else if trust_score < 75.0 {
        EngineMode::Drafts
    } else {
        EngineMode::AutopilotLimited
    }
}
