#![allow(dead_code)]

use serde::{Deserialize, Serialize};
use sqlx::FromRow;

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct WorkItem {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_type: String,
    pub surface: String,
    pub status: String,
    pub priority: i64,
    pub dedupe_key: String,
    pub inputs_json: String,
    pub state_json: String,
    pub due_at: Option<String>,
    pub snoozed_until: Option<String>,
    pub risk_level: String,
    pub confidence_score: f64,
    pub requires_approval: bool,
    pub customer_title: String,
    pub customer_summary: String,
    pub internal_title: String,
    pub internal_notes: String,
    pub links_json: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct ActionRecommendation {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_item_id: i64,
    pub action_kind: String,
    pub payload_json: String,
    pub preview_effects_json: String,
    pub status: String,
    pub requires_confirm: bool,
    pub approval_request_id: Option<i64>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct ApprovalRequest {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_item_id: i64,
    pub requested_by: String,
    pub status: String,
    pub approved_by: Option<i64>,
    pub reason_required: bool,
    pub reason_text: Option<String>,
    pub expires_at: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct RationaleCard {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_item_id: i64,
    pub sections_json: String,
    pub customer_safe_text: String,
    pub generated_at: String,
    pub version: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Claim {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_item_id: i64,
    pub statement: String,
    pub confidence: f64,
    pub verification_status: String,
    pub source_quality_score: f64,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Evidence {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_item_id: i64,
    pub url: String,
    pub title: String,
    pub retrieved_at: String,
    pub excerpt_hash: String,
    pub credibility_flags: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct ClaimEvidence {
    pub id: i64,
    pub claim_id: i64,
    pub evidence_id: i64,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct AgentRun {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_item_id: Option<i64>,
    pub agent_name: String,
    pub status: String,
    pub started_at: Option<String>,
    pub finished_at: Option<String>,
    pub max_tokens: i64,
    pub max_tool_calls: i64,
    pub max_seconds: i64,
    pub inputs_hash: String,
    pub outputs_json: Option<String>,
    pub error_code: Option<String>,
    pub error_detail: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Job {
    pub id: String,
    pub tenant_id: i64,
    pub kind: String,
    pub status: String,
    pub priority: i64,
    pub input_json: String,
    pub output_json: Option<String>,
    pub error_detail: Option<String>,
    pub budget_json: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct ToolCall {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub agent_run_id: Option<i64>,
    pub tool_name: String,
    pub provider: String,
    pub request_meta: String,
    pub response_meta: String,
    pub tokens_used: i64,
    pub cost_estimate: f64,
    pub duration_ms: i64,
    pub allowlisted: bool,
    pub blocked_reason: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct CircuitBreakerEvent {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub breaker_type: String,
    pub threshold: f64,
    pub observed_value: f64,
    pub action_taken: String,
    pub related_work_item_id: Option<i64>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Snapshot {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub generated_at: String,
    pub payload_json: String,
    pub stale_after_minutes: i64,
    pub source_version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct QueueSnapshot {
    pub id: i64,
    pub tenant_id: i64,
    pub snapshot_json: String,
    pub generated_at: String,
    pub stale_after_seconds: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct PolicyRow {
    pub tenant_id: i64,
    pub mode: String,
    pub breaker_thresholds_json: String,
    pub allowlists_json: String,
    pub budgets_json: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct AiSettingsRow {
    pub id: i64,
    pub business_id: i64,
    pub ai_enabled: bool,
    pub kill_switch: bool,
    pub ai_mode: String,
    pub velocity_limit_per_minute: i64,
    pub value_breaker_threshold: String,
    pub anomaly_stddev_threshold: String,
    pub trust_downgrade_rejection_rate: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct BusinessPolicyRow {
    pub id: i64,
    pub business_id: i64,
    pub materiality_threshold: String,
    pub risk_appetite: String,
    pub commingling_risk_vendors_json: String,
    pub related_entities_json: String,
    pub intercompany_enabled: bool,
    pub sector_archetype: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct AuditLog {
    pub id: i64,
    pub tenant_id: i64,
    pub business_id: i64,
    pub actor_id: Option<i64>,
    pub actor_label: String,
    pub action: String,
    pub target_type: String,
    pub target_id: String,
    pub payload_json: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkItemSeed {
    pub tenant_id: i64,
    pub business_id: i64,
    pub work_type: String,
    pub surface: String,
    pub status: String,
    pub priority: i64,
    pub dedupe_key: String,
    pub inputs: serde_json::Value,
    pub state: serde_json::Value,
    pub due_at: Option<String>,
    pub snoozed_until: Option<String>,
    pub risk_level: String,
    pub confidence_score: f64,
    pub requires_approval: bool,
    pub customer_title: String,
    pub customer_summary: String,
    pub internal_title: String,
    pub internal_notes: String,
    pub links: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecommendationSeed {
    pub action_kind: String,
    pub payload: serde_json::Value,
    pub preview_effects: serde_json::Value,
    pub status: String,
    pub requires_confirm: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CockpitQueueItem {
    pub id: i64,
    pub work_type: String,
    pub surface: String,
    pub status: String,
    pub risk_level: String,
    pub title: String,
    pub summary: String,
    pub action_id: Option<i64>,
    pub target_url: Option<String>,
    pub due_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CockpitQueues {
    pub generated_at: String,
    pub mode: String,
    pub trust_score: f64,
    pub stats: serde_json::Value,
    pub ready_queue: Vec<CockpitQueueItem>,
    pub needs_attention_queue: Vec<CockpitQueueItem>,
    pub job_totals: Option<serde_json::Value>,
    pub job_by_agent: Option<Vec<serde_json::Value>>,
    pub top_blockers: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentOutput {
    pub signals: Vec<serde_json::Value>,
    pub recommendations: Vec<serde_json::Value>,
    pub evidence_refs: Vec<String>,
    pub work_items: Vec<WorkItemSeed>,
}

impl AgentOutput {
    pub fn empty() -> Self {
        Self {
            signals: Vec::new(),
            recommendations: Vec::new(),
            evidence_refs: Vec::new(),
            work_items: Vec::new(),
        }
    }
}
