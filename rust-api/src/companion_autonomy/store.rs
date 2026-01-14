use serde_json::Value;
use sqlx::SqlitePool;
use uuid::Uuid;

use crate::companion_autonomy::models::{
    ActionRecommendation, AgentRun, ApprovalRequest, AiSettingsRow, BusinessPolicyRow,
    CockpitQueueItem, CockpitQueues, Evidence, PolicyRow, QueueSnapshot, RationaleCard,
    RecommendationSeed, WorkItem, WorkItemSeed,
};
use crate::companion_autonomy::policy::{derive_engine_mode, trust_score};
use crate::companion_autonomy::now_utc_str;

pub async fn list_business_ids(pool: &SqlitePool) -> Result<Vec<i64>, sqlx::Error> {
    let rows = sqlx::query_scalar::<_, i64>("SELECT id FROM core_business WHERE is_deleted = 0")
        .fetch_all(pool)
        .await?;
    Ok(rows)
}

pub async fn business_ai_enabled(pool: &SqlitePool, business_id: i64) -> Result<Option<bool>, sqlx::Error> {
    sqlx::query_scalar::<_, i64>(
        "SELECT ai_companion_enabled FROM core_business WHERE id = ?"
    )
    .bind(business_id)
    .fetch_optional(pool)
    .await
    .map(|row| row.map(|value| value != 0))
}

pub async fn insert_job(
    pool: &SqlitePool,
    tenant_id: i64,
    kind: &str,
    status: &str,
    priority: i64,
    input_json: &Value,
    budget_json: &Value,
) -> Result<String, sqlx::Error> {
    let job_id = Uuid::new_v4().to_string();
    let input_json = serde_json::to_string(input_json).unwrap_or_else(|_| "{}".to_string());
    let budget_json = serde_json::to_string(budget_json).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "INSERT INTO companion_autonomy_jobs (
            id, tenant_id, kind, status, priority, input_json, output_json, error_detail, budget_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, datetime('now'), datetime('now'))"
    )
    .bind(&job_id)
    .bind(tenant_id)
    .bind(kind)
    .bind(status)
    .bind(priority)
    .bind(input_json)
    .bind(budget_json)
    .execute(pool)
    .await?;
    Ok(job_id)
}

pub async fn update_job_status(
    pool: &SqlitePool,
    job_id: &str,
    status: &str,
    output_json: Option<&Value>,
    error_detail: Option<&str>,
) -> Result<(), sqlx::Error> {
    let output_json = output_json.map(|value| serde_json::to_string(value).unwrap_or_else(|_| "{}".to_string()));
    sqlx::query(
        "UPDATE companion_autonomy_jobs
         SET status = ?, output_json = COALESCE(?, output_json), error_detail = ?, updated_at = datetime('now')
         WHERE id = ?"
    )
    .bind(status)
    .bind(output_json)
    .bind(error_detail)
    .bind(job_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn job_totals(pool: &SqlitePool, tenant_id: i64) -> Result<Value, sqlx::Error> {
    let row = sqlx::query_as::<_, (i64, i64, i64, i64, i64, i64)>(
        "SELECT
            COALESCE(SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END), 0) AS queued,
            COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0) AS running,
            COALESCE(SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END), 0) AS blocked,
            COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed,
            COALESCE(SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END), 0) AS succeeded,
            COALESCE(SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END), 0) AS canceled
         FROM companion_autonomy_jobs
         WHERE tenant_id = ?"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
    .unwrap_or((0, 0, 0, 0, 0, 0));

    Ok(serde_json::json!({
        "queued": row.0,
        "running": row.1,
        "blocked": row.2,
        "failed": row.3,
        "succeeded": row.4,
        "canceled": row.5
    }))
}

pub async fn job_counts_by_kind(pool: &SqlitePool, tenant_id: i64) -> Result<Vec<Value>, sqlx::Error> {
    let rows = sqlx::query_as::<_, (String, i64, i64, i64)>(
        "SELECT kind,
            COALESCE(SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END), 0) AS queued,
            COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0) AS running,
            COALESCE(SUM(CASE WHEN status IN ('blocked', 'failed') THEN 1 ELSE 0 END), 0) AS blocked
         FROM companion_autonomy_jobs
         WHERE tenant_id = ?
         GROUP BY kind"
    )
    .bind(tenant_id)
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|(kind, queued, running, blocked)| {
            serde_json::json!({
                "agent": kind,
                "queued": queued,
                "running": running,
                "blocked": blocked
            })
        })
        .collect())
}

pub async fn job_top_blockers(pool: &SqlitePool, tenant_id: i64) -> Result<Vec<Value>, sqlx::Error> {
    let rows = sqlx::query_as::<_, (String, String, Option<String>, String)>(
        "SELECT kind, status, error_detail, updated_at
         FROM companion_autonomy_jobs
         WHERE tenant_id = ? AND status IN ('blocked', 'failed')
         ORDER BY updated_at DESC
         LIMIT 5"
    )
    .bind(tenant_id)
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|(kind, status, error_detail, updated_at)| {
            serde_json::json!({
                "kind": kind,
                "status": status,
                "reason": error_detail.unwrap_or_else(|| "Blocked".to_string()),
                "updated_at": updated_at
            })
        })
        .collect())
}

pub async fn insert_queue_snapshot(
    pool: &SqlitePool,
    tenant_id: i64,
    payload: &Value,
    stale_after_seconds: i64,
) -> Result<(), sqlx::Error> {
    let payload_json = serde_json::to_string(payload).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "INSERT INTO companion_autonomy_queue_snapshot (
            tenant_id, snapshot_json, generated_at, stale_after_seconds
        ) VALUES (?, ?, datetime('now'), ?)"
    )
    .bind(tenant_id)
    .bind(payload_json)
    .bind(stale_after_seconds)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn latest_queue_snapshot(pool: &SqlitePool, tenant_id: i64) -> Result<Option<QueueSnapshot>, sqlx::Error> {
    sqlx::query_as::<_, QueueSnapshot>(
        "SELECT * FROM companion_autonomy_queue_snapshot
         WHERE tenant_id = ?
         ORDER BY generated_at DESC
         LIMIT 1"
    )
    .bind(tenant_id)
    .fetch_optional(pool)
    .await
}

pub async fn fetch_policy(pool: &SqlitePool, tenant_id: i64) -> Result<Option<PolicyRow>, sqlx::Error> {
    sqlx::query_as::<_, PolicyRow>(
        "SELECT * FROM companion_autonomy_policy WHERE tenant_id = ?"
    )
    .bind(tenant_id)
    .fetch_optional(pool)
    .await
}

pub async fn fetch_ai_settings(pool: &SqlitePool, business_id: i64) -> Result<Option<AiSettingsRow>, sqlx::Error> {
    sqlx::query_as::<_, AiSettingsRow>(
        "SELECT * FROM companion_ai_settings WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_optional(pool)
    .await
}

#[allow(clippy::too_many_arguments)]
pub async fn upsert_ai_settings(
    pool: &SqlitePool,
    business_id: i64,
    ai_enabled: bool,
    kill_switch: bool,
    ai_mode: &str,
    velocity_limit_per_minute: i64,
    value_breaker_threshold: &str,
    anomaly_stddev_threshold: &str,
    trust_downgrade_rejection_rate: &str,
) -> Result<AiSettingsRow, sqlx::Error> {
    sqlx::query(
        "INSERT INTO companion_ai_settings (
            business_id, ai_enabled, kill_switch, ai_mode, velocity_limit_per_minute,
            value_breaker_threshold, anomaly_stddev_threshold, trust_downgrade_rejection_rate,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(business_id) DO UPDATE SET
            ai_enabled = excluded.ai_enabled,
            kill_switch = excluded.kill_switch,
            ai_mode = excluded.ai_mode,
            velocity_limit_per_minute = excluded.velocity_limit_per_minute,
            value_breaker_threshold = excluded.value_breaker_threshold,
            anomaly_stddev_threshold = excluded.anomaly_stddev_threshold,
            trust_downgrade_rejection_rate = excluded.trust_downgrade_rejection_rate,
            updated_at = datetime('now')"
    )
    .bind(business_id)
    .bind(ai_enabled)
    .bind(kill_switch)
    .bind(ai_mode)
    .bind(velocity_limit_per_minute)
    .bind(value_breaker_threshold)
    .bind(anomaly_stddev_threshold)
    .bind(trust_downgrade_rejection_rate)
    .execute(pool)
    .await?;

    sqlx::query_as::<_, AiSettingsRow>(
        "SELECT * FROM companion_ai_settings WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
}

pub async fn fetch_business_policy(pool: &SqlitePool, business_id: i64) -> Result<Option<BusinessPolicyRow>, sqlx::Error> {
    sqlx::query_as::<_, BusinessPolicyRow>(
        "SELECT * FROM companion_business_policy WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_optional(pool)
    .await
}

pub async fn upsert_business_policy(
    pool: &SqlitePool,
    business_id: i64,
    materiality_threshold: &str,
    risk_appetite: &str,
    commingling_risk_vendors_json: &str,
    related_entities_json: &str,
    intercompany_enabled: bool,
    sector_archetype: &str,
) -> Result<BusinessPolicyRow, sqlx::Error> {
    sqlx::query(
        "INSERT INTO companion_business_policy (
            business_id, materiality_threshold, risk_appetite,
            commingling_risk_vendors_json, related_entities_json,
            intercompany_enabled, sector_archetype, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(business_id) DO UPDATE SET
            materiality_threshold = excluded.materiality_threshold,
            risk_appetite = excluded.risk_appetite,
            commingling_risk_vendors_json = excluded.commingling_risk_vendors_json,
            related_entities_json = excluded.related_entities_json,
            intercompany_enabled = excluded.intercompany_enabled,
            sector_archetype = excluded.sector_archetype,
            updated_at = datetime('now')"
    )
    .bind(business_id)
    .bind(materiality_threshold)
    .bind(risk_appetite)
    .bind(commingling_risk_vendors_json)
    .bind(related_entities_json)
    .bind(intercompany_enabled)
    .bind(sector_archetype)
    .execute(pool)
    .await?;

    sqlx::query_as::<_, BusinessPolicyRow>(
        "SELECT * FROM companion_business_policy WHERE business_id = ?"
    )
    .bind(business_id)
    .fetch_one(pool)
    .await
}

pub async fn upsert_policy(
    pool: &SqlitePool,
    tenant_id: i64,
    mode: &str,
    breaker_thresholds: &Value,
    allowlists: &Value,
    budgets: &Value,
) -> Result<(), sqlx::Error> {
    let breaker_json = serde_json::to_string(breaker_thresholds).unwrap_or_else(|_| "{}".to_string());
    let allowlists_json = serde_json::to_string(allowlists).unwrap_or_else(|_| "{}".to_string());
    let budgets_json = serde_json::to_string(budgets).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "INSERT INTO companion_autonomy_policy (
            tenant_id, mode, breaker_thresholds_json, allowlists_json, budgets_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(tenant_id) DO UPDATE SET
            mode = excluded.mode,
            breaker_thresholds_json = excluded.breaker_thresholds_json,
            allowlists_json = excluded.allowlists_json,
            budgets_json = excluded.budgets_json,
            updated_at = datetime('now')"
    )
    .bind(tenant_id)
    .bind(mode)
    .bind(breaker_json)
    .bind(allowlists_json)
    .bind(budgets_json)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn upsert_work_item(pool: &SqlitePool, seed: &WorkItemSeed) -> Result<WorkItem, sqlx::Error> {
    let inputs_json = serde_json::to_string(&seed.inputs).unwrap_or_else(|_| "{}".to_string());
    let state_json = serde_json::to_string(&seed.state).unwrap_or_else(|_| "{}".to_string());
    let links_json = serde_json::to_string(&seed.links).unwrap_or_else(|_| "{}".to_string());

    sqlx::query(
        "INSERT INTO companion_autonomy_work_items (
            tenant_id, business_id, work_type, surface, status, priority, dedupe_key,
            inputs_json, state_json, due_at, snoozed_until, risk_level, confidence_score,
            requires_approval, customer_title, customer_summary, internal_title, internal_notes,
            links_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        ON CONFLICT(tenant_id, dedupe_key) DO UPDATE SET
            status = excluded.status,
            priority = excluded.priority,
            state_json = excluded.state_json,
            due_at = excluded.due_at,
            snoozed_until = excluded.snoozed_until,
            risk_level = excluded.risk_level,
            confidence_score = excluded.confidence_score,
            requires_approval = excluded.requires_approval,
            customer_title = excluded.customer_title,
            customer_summary = excluded.customer_summary,
            internal_title = excluded.internal_title,
            internal_notes = excluded.internal_notes,
            links_json = excluded.links_json,
            updated_at = datetime('now')"
    )
    .bind(seed.tenant_id)
    .bind(seed.business_id)
    .bind(&seed.work_type)
    .bind(&seed.surface)
    .bind(&seed.status)
    .bind(seed.priority)
    .bind(&seed.dedupe_key)
    .bind(inputs_json)
    .bind(state_json)
    .bind(seed.due_at.as_deref())
    .bind(seed.snoozed_until.as_deref())
    .bind(&seed.risk_level)
    .bind(seed.confidence_score)
    .bind(seed.requires_approval)
    .bind(&seed.customer_title)
    .bind(&seed.customer_summary)
    .bind(&seed.internal_title)
    .bind(&seed.internal_notes)
    .bind(links_json)
    .execute(pool)
    .await?;

    sqlx::query_as::<_, WorkItem>(
        "SELECT * FROM companion_autonomy_work_items WHERE tenant_id = ? AND dedupe_key = ?"
    )
    .bind(seed.tenant_id)
    .bind(&seed.dedupe_key)
    .fetch_one(pool)
    .await
}

pub async fn upsert_action_recommendation(
    pool: &SqlitePool,
    work_item_id: i64,
    seed: &RecommendationSeed,
    tenant_id: i64,
    business_id: i64,
) -> Result<ActionRecommendation, sqlx::Error> {
    let payload_json = serde_json::to_string(&seed.payload).unwrap_or_else(|_| "{}".to_string());
    let preview_json = serde_json::to_string(&seed.preview_effects).unwrap_or_else(|_| "{}".to_string());

    sqlx::query(
        "INSERT INTO companion_autonomy_action_recommendations (
            tenant_id, business_id, work_item_id, action_kind, payload_json, preview_effects_json,
            status, requires_confirm, approval_request_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now'))
        ON CONFLICT(work_item_id, action_kind) DO UPDATE SET
            payload_json = excluded.payload_json,
            preview_effects_json = excluded.preview_effects_json,
            status = excluded.status,
            requires_confirm = excluded.requires_confirm,
            updated_at = datetime('now')"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(work_item_id)
    .bind(&seed.action_kind)
    .bind(payload_json)
    .bind(preview_json)
    .bind(&seed.status)
    .bind(seed.requires_confirm)
    .execute(pool)
    .await?;

    sqlx::query_as::<_, ActionRecommendation>(
        "SELECT * FROM companion_autonomy_action_recommendations WHERE work_item_id = ? AND action_kind = ?"
    )
    .bind(work_item_id)
    .bind(&seed.action_kind)
    .fetch_one(pool)
    .await
}

pub async fn insert_rationale_card(
    pool: &SqlitePool,
    work_item_id: i64,
    tenant_id: i64,
    business_id: i64,
    sections: &Value,
    customer_safe_text: &str,
) -> Result<RationaleCard, sqlx::Error> {
    let sections_json = serde_json::to_string(sections).unwrap_or_else(|_| "{}".to_string());
    let version: i64 = sqlx::query_scalar(
        "SELECT COALESCE(MAX(version), 0) FROM companion_autonomy_rationale_cards WHERE work_item_id = ?"
    )
    .bind(work_item_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0);

    let next_version = version + 1;

    sqlx::query(
        "INSERT INTO companion_autonomy_rationale_cards (
            tenant_id, business_id, work_item_id, sections_json, customer_safe_text, generated_at, version
        ) VALUES (?, ?, ?, ?, ?, datetime('now'), ?)"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(work_item_id)
    .bind(sections_json)
    .bind(customer_safe_text)
    .bind(next_version)
    .execute(pool)
    .await?;

    sqlx::query_as::<_, RationaleCard>(
        "SELECT * FROM companion_autonomy_rationale_cards WHERE work_item_id = ? AND version = ?"
    )
    .bind(work_item_id)
    .bind(next_version)
    .fetch_one(pool)
    .await
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_claim(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    work_item_id: i64,
    statement: &str,
    confidence: f64,
    verification_status: &str,
    source_quality_score: f64,
) -> Result<i64, sqlx::Error> {
    let result = sqlx::query(
        "INSERT INTO companion_autonomy_claims (
            tenant_id, business_id, work_item_id, statement, confidence,
            verification_status, source_quality_score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(work_item_id)
    .bind(statement)
    .bind(confidence)
    .bind(verification_status)
    .bind(source_quality_score)
    .execute(pool)
    .await?;
    Ok(result.last_insert_rowid())
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_evidence(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    work_item_id: i64,
    url: &str,
    title: &str,
    excerpt_hash: &str,
    credibility_flags: &str,
) -> Result<i64, sqlx::Error> {
    let result = sqlx::query(
        "INSERT INTO companion_autonomy_evidence (
            tenant_id, business_id, work_item_id, url, title, retrieved_at, excerpt_hash, credibility_flags, created_at
        ) VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(work_item_id)
    .bind(url)
    .bind(title)
    .bind(excerpt_hash)
    .bind(credibility_flags)
    .execute(pool)
    .await?;
    Ok(result.last_insert_rowid())
}

pub async fn link_claim_evidence(
    pool: &SqlitePool,
    claim_id: i64,
    evidence_id: i64,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT OR IGNORE INTO companion_autonomy_claim_evidence (claim_id, evidence_id, created_at)
         VALUES (?, ?, datetime('now'))"
    )
    .bind(claim_id)
    .bind(evidence_id)
    .execute(pool)
    .await?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_audit_log(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    actor_id: Option<i64>,
    actor_label: &str,
    action: &str,
    target_type: &str,
    target_id: &str,
    payload: &Value,
) -> Result<(), sqlx::Error> {
    let payload_json = serde_json::to_string(payload).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "INSERT INTO companion_autonomy_audit_log (
            tenant_id, business_id, actor_id, actor_label, action, target_type, target_id, payload_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(actor_id)
    .bind(actor_label)
    .bind(action)
    .bind(target_type)
    .bind(target_id)
    .bind(payload_json)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn latest_audit_action_time(
    pool: &SqlitePool,
    tenant_id: i64,
    action: &str,
) -> Result<Option<String>, sqlx::Error> {
    let row = sqlx::query_as::<_, (String,)>(
        "SELECT created_at FROM companion_autonomy_audit_log
         WHERE tenant_id = ? AND action = ?
         ORDER BY created_at DESC
         LIMIT 1"
    )
    .bind(tenant_id)
    .bind(action)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|(created_at,)| created_at))
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_agent_run(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    work_item_id: Option<i64>,
    agent_name: &str,
    inputs_hash: &str,
    max_tokens: i64,
    max_tool_calls: i64,
    max_seconds: i64,
) -> Result<i64, sqlx::Error> {
    let result = sqlx::query(
        "INSERT INTO companion_autonomy_agent_runs (
            tenant_id, business_id, work_item_id, agent_name, status, started_at, finished_at,
            max_tokens, max_tool_calls, max_seconds, inputs_hash, outputs_json, error_code, error_detail, created_at
        ) VALUES (?, ?, ?, ?, 'queued', NULL, NULL, ?, ?, ?, ?, NULL, NULL, NULL, datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(work_item_id)
    .bind(agent_name)
    .bind(max_tokens)
    .bind(max_tool_calls)
    .bind(max_seconds)
    .bind(inputs_hash)
    .execute(pool)
    .await?;

    Ok(result.last_insert_rowid())
}

pub async fn mark_agent_run_started(pool: &SqlitePool, run_id: i64) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE companion_autonomy_agent_runs
         SET status = 'in_progress', started_at = datetime('now')
         WHERE id = ?"
    )
    .bind(run_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn complete_agent_run(
    pool: &SqlitePool,
    run_id: i64,
    outputs: &Value,
) -> Result<(), sqlx::Error> {
    let outputs_json = serde_json::to_string(outputs).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "UPDATE companion_autonomy_agent_runs
         SET status = 'completed', finished_at = datetime('now'), outputs_json = ?
         WHERE id = ?"
    )
    .bind(outputs_json)
    .bind(run_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn fail_agent_run(
    pool: &SqlitePool,
    run_id: i64,
    error_code: &str,
    error_detail: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE companion_autonomy_agent_runs
         SET status = 'failed', finished_at = datetime('now'), error_code = ?, error_detail = ?
         WHERE id = ?"
    )
    .bind(error_code)
    .bind(error_detail)
    .bind(run_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn list_agent_runs(
    pool: &SqlitePool,
    tenant_id: i64,
    limit: i64,
) -> Result<Vec<AgentRun>, sqlx::Error> {
    sqlx::query_as::<_, AgentRun>(
        "SELECT * FROM companion_autonomy_agent_runs
         WHERE tenant_id = ?
         ORDER BY created_at DESC
         LIMIT ?"
    )
    .bind(tenant_id)
    .bind(limit)
    .fetch_all(pool)
    .await
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_tool_call(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    agent_run_id: Option<i64>,
    tool_name: &str,
    provider: &str,
    request_meta: &Value,
    response_meta: &Value,
    tokens_used: i64,
    cost_estimate: f64,
    duration_ms: i64,
    allowlisted: bool,
    blocked_reason: Option<&str>,
) -> Result<(), sqlx::Error> {
    let request_json = serde_json::to_string(request_meta).unwrap_or_else(|_| "{}".to_string());
    let response_json = serde_json::to_string(response_meta).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "INSERT INTO companion_autonomy_tool_calls (
            tenant_id, business_id, agent_run_id, tool_name, provider, request_meta,
            response_meta, tokens_used, cost_estimate, duration_ms, allowlisted, blocked_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(agent_run_id)
    .bind(tool_name)
    .bind(provider)
    .bind(request_json)
    .bind(response_json)
    .bind(tokens_used)
    .bind(cost_estimate)
    .bind(duration_ms)
    .bind(allowlisted)
    .bind(blocked_reason)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn tool_usage_last_day(pool: &SqlitePool, tenant_id: i64) -> Result<(i64, i64), sqlx::Error> {
    let row = sqlx::query_as::<_, (i64, i64)>(
        "SELECT COUNT(*), COALESCE(SUM(tokens_used), 0)
         FROM companion_autonomy_tool_calls
         WHERE tenant_id = ? AND created_at >= datetime('now', '-1 day')"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await?;
    Ok(row)
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_breaker_event(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    breaker_type: &str,
    threshold: f64,
    observed_value: f64,
    action_taken: &str,
    related_work_item_id: Option<i64>,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO companion_autonomy_circuit_breaker_events (
            tenant_id, business_id, breaker_type, threshold, observed_value, action_taken, related_work_item_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(breaker_type)
    .bind(threshold)
    .bind(observed_value)
    .bind(action_taken)
    .bind(related_work_item_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn breaker_events_last_day(pool: &SqlitePool, tenant_id: i64) -> Result<i64, sqlx::Error> {
    sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_circuit_breaker_events
         WHERE tenant_id = ? AND created_at >= datetime('now', '-1 day')"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
}

pub async fn action_outcomes(pool: &SqlitePool, tenant_id: i64) -> Result<(i64, i64), sqlx::Error> {
    let applied: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_action_recommendations
         WHERE tenant_id = ? AND status = 'applied'"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0);

    let dismissed: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_action_recommendations
         WHERE tenant_id = ? AND status IN ('rejected', 'dismissed')"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0);

    Ok((applied, dismissed))
}

pub async fn action_outcomes_last_day(
    pool: &SqlitePool,
    tenant_id: i64,
) -> Result<(i64, i64), sqlx::Error> {
    let applied: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_action_recommendations
         WHERE tenant_id = ? AND status = 'applied'
           AND updated_at >= datetime('now', '-1 day')"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0);

    let dismissed: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_action_recommendations
         WHERE tenant_id = ? AND status IN ('rejected', 'dismissed')
           AND updated_at >= datetime('now', '-1 day')"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0);

    Ok((applied, dismissed))
}

pub async fn fetch_cockpit_queues(pool: &SqlitePool, tenant_id: i64) -> Result<CockpitQueues, sqlx::Error> {
    let ready_queue = list_queue_items(pool, tenant_id, "ready").await?;
    let needs_attention_queue = list_queue_items(pool, tenant_id, "needs_attention").await?;

    let stats = queue_stats(pool, tenant_id).await?;
    let (applied, dismissed) = action_outcomes(pool, tenant_id).await?;
    let breaker_events = breaker_events_last_day(pool, tenant_id).await.unwrap_or(0);
    let score = trust_score(applied, dismissed, breaker_events);
    let policy_mode = fetch_policy(pool, tenant_id)
        .await
        .ok()
        .flatten()
        .map(|row| row.mode);
    let mode = policy_mode.unwrap_or_else(|| derive_engine_mode(score, breaker_events > 0).as_str().to_string());
    let job_totals = job_totals(pool, tenant_id).await.ok();
    let job_by_agent = job_counts_by_kind(pool, tenant_id).await.ok();
    let top_blockers = job_top_blockers(pool, tenant_id).await.ok();

    Ok(CockpitQueues {
        generated_at: now_utc_str(),
        mode,
        trust_score: score,
        stats,
        ready_queue,
        needs_attention_queue,
        job_totals,
        job_by_agent,
        top_blockers,
    })
}

type CockpitQueueRow = (
    i64,
    String,
    String,
    String,
    String,
    String,
    String,
    String,
    Option<String>,
    Option<i64>,
);

async fn list_queue_items(
    pool: &SqlitePool,
    tenant_id: i64,
    queue: &str,
) -> Result<Vec<CockpitQueueItem>, sqlx::Error> {
    let (filter, limit, action_kind) = match queue {
        "ready" => (
            "w.status IN ('open', 'ready') AND w.requires_approval = 0 AND w.risk_level IN ('low', 'medium')",
            20,
            "apply",
        ),
        _ => (
            "w.status IN ('open', 'waiting_approval') AND (w.requires_approval = 1 OR w.risk_level = 'high')",
            20,
            "review",
        ),
    };

    let query = format!(
        "SELECT w.id, w.work_type, w.surface, w.status, w.risk_level, w.customer_title, w.customer_summary,
                w.links_json, w.due_at, a.id
         FROM companion_autonomy_work_items w
         LEFT JOIN companion_autonomy_action_recommendations a
           ON w.id = a.work_item_id AND a.action_kind = '{}' AND a.status = 'proposed'
         WHERE w.tenant_id = ? AND {}
         ORDER BY w.priority DESC, w.created_at DESC
         LIMIT {}",
        action_kind, filter, limit
    );

    let rows: Vec<CockpitQueueRow> = sqlx::query_as(&query)
        .bind(tenant_id)
        .fetch_all(pool)
        .await?;

    let items = rows
        .into_iter()
        .map(|(id, work_type, surface, status, risk_level, title, summary, links_json, due_at, action_id)| {
            let target_url = serde_json::from_str::<Value>(&links_json)
                .ok()
                .and_then(|v| v.get("target_url").and_then(|u| u.as_str()).map(|s| s.to_string()));
            CockpitQueueItem {
                id,
                work_type,
                surface,
                status,
                risk_level,
                title,
                summary,
                action_id,
                target_url,
                due_at,
            }
        })
        .collect();

    Ok(items)
}

async fn queue_stats(pool: &SqlitePool, tenant_id: i64) -> Result<Value, sqlx::Error> {
    let row = sqlx::query_as::<_, (i64, i64, i64)>(
        "SELECT
            COALESCE(SUM(CASE WHEN status IN ('open', 'ready') AND requires_approval = 0 AND risk_level IN ('low', 'medium') THEN 1 ELSE 0 END), 0) AS ready_count,
            COALESCE(SUM(CASE WHEN status IN ('open', 'waiting_approval') AND (requires_approval = 1 OR risk_level = 'high') THEN 1 ELSE 0 END), 0) AS attention_count,
            COALESCE(SUM(CASE WHEN status = 'waiting_approval' THEN 1 ELSE 0 END), 0) AS waiting_approval
         FROM companion_autonomy_work_items
         WHERE tenant_id = ?"
    )
    .bind(tenant_id)
    .fetch_one(pool)
    .await
    .unwrap_or((0, 0, 0));

    let (applied_last_day, dismissed_last_day) = action_outcomes_last_day(pool, tenant_id)
        .await
        .unwrap_or((0, 0));
    let breaker_events = breaker_events_last_day(pool, tenant_id).await.unwrap_or(0);

    Ok(serde_json::json!({
        "ready": row.0,
        "needs_attention": row.1,
        "waiting_approval": row.2,
        "applied_last_day": applied_last_day,
        "dismissed_last_day": dismissed_last_day,
        "breaker_events_last_day": breaker_events
    }))
}

pub async fn insert_snapshot(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    payload: &Value,
    stale_after_minutes: i64,
    source_version: &str,
) -> Result<(), sqlx::Error> {
    let payload_json = serde_json::to_string(payload).unwrap_or_else(|_| "{}".to_string());
    sqlx::query(
        "INSERT INTO companion_autonomy_snapshots (
            tenant_id, business_id, generated_at, payload_json, stale_after_minutes, source_version
        ) VALUES (?, ?, datetime('now'), ?, ?, ?)"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(payload_json)
    .bind(stale_after_minutes)
    .bind(source_version)
    .execute(pool)
    .await?;
    Ok(())
}

#[allow(dead_code)]
pub async fn latest_snapshot(pool: &SqlitePool, tenant_id: i64) -> Result<Option<Value>, sqlx::Error> {
    let row = sqlx::query_as::<_, (String,)>(
        "SELECT payload_json FROM companion_autonomy_snapshots
         WHERE tenant_id = ?
         ORDER BY generated_at DESC
         LIMIT 1"
    )
    .bind(tenant_id)
    .fetch_optional(pool)
    .await?;

    Ok(row.and_then(|r| serde_json::from_str(&r.0).ok()))
}

pub async fn dismiss_work_item(
    pool: &SqlitePool,
    tenant_id: i64,
    work_item_id: i64,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE companion_autonomy_work_items
         SET status = 'dismissed', updated_at = datetime('now')
         WHERE id = ? AND tenant_id = ? AND status NOT IN ('dismissed', 'applied')"
    )
    .bind(work_item_id)
    .bind(tenant_id)
    .execute(pool)
    .await?;
    let updated = result.rows_affected() > 0;
    if updated {
        let _ = sqlx::query(
            "UPDATE companion_autonomy_action_recommendations
             SET status = 'dismissed', updated_at = datetime('now')
             WHERE work_item_id = ? AND tenant_id = ?"
        )
        .bind(work_item_id)
        .bind(tenant_id)
        .execute(pool)
        .await;
    }
    Ok(updated)
}

pub async fn snooze_work_item(
    pool: &SqlitePool,
    tenant_id: i64,
    work_item_id: i64,
    until: &str,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE companion_autonomy_work_items
         SET status = 'snoozed', snoozed_until = ?, updated_at = datetime('now')
         WHERE id = ? AND tenant_id = ? AND status NOT IN ('dismissed', 'applied')"
    )
    .bind(until)
    .bind(work_item_id)
    .bind(tenant_id)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}

#[allow(clippy::too_many_arguments)]
pub async fn create_approval_request(
    pool: &SqlitePool,
    tenant_id: i64,
    business_id: i64,
    work_item_id: i64,
    requested_by: &str,
    reason_required: bool,
    reason_text: Option<&str>,
    expires_at: Option<&str>,
) -> Result<ApprovalRequest, sqlx::Error> {
    let result = sqlx::query(
        "INSERT INTO companion_autonomy_approval_requests (
            tenant_id, business_id, work_item_id, requested_by, status, approved_by,
            reason_required, reason_text, expires_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'pending', NULL, ?, ?, ?, datetime('now'), datetime('now'))"
    )
    .bind(tenant_id)
    .bind(business_id)
    .bind(work_item_id)
    .bind(requested_by)
    .bind(reason_required)
    .bind(reason_text)
    .bind(expires_at)
    .execute(pool)
    .await?;

    let id = result.last_insert_rowid();

    sqlx::query_as::<_, ApprovalRequest>(
        "SELECT * FROM companion_autonomy_approval_requests WHERE id = ?"
    )
    .bind(id)
    .fetch_one(pool)
    .await
}

pub async fn set_approval_status(
    pool: &SqlitePool,
    tenant_id: i64,
    approval_id: i64,
    status: &str,
    approved_by: Option<i64>,
    reason_text: Option<&str>,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE companion_autonomy_approval_requests
         SET status = ?, approved_by = ?, reason_text = COALESCE(?, reason_text), updated_at = datetime('now')
         WHERE id = ? AND tenant_id = ?"
    )
    .bind(status)
    .bind(approved_by)
    .bind(reason_text)
    .bind(approval_id)
    .bind(tenant_id)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}

pub async fn apply_action(
    pool: &SqlitePool,
    tenant_id: i64,
    action_id: i64,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE companion_autonomy_action_recommendations
         SET status = 'applied', updated_at = datetime('now')
         WHERE id = ? AND tenant_id = ? AND status = 'proposed'
           AND work_item_id IN (
             SELECT id FROM companion_autonomy_work_items
             WHERE tenant_id = ? AND status IN ('open', 'ready', 'waiting_approval')
           )"
    )
    .bind(action_id)
    .bind(tenant_id)
    .bind(tenant_id)
    .execute(pool)
    .await?;

    Ok(result.rows_affected() > 0)
}

pub async fn update_work_item_status(
    pool: &SqlitePool,
    work_item_id: i64,
    tenant_id: i64,
    status: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE companion_autonomy_work_items
         SET status = ?, updated_at = datetime('now')
         WHERE id = ? AND tenant_id = ?"
    )
    .bind(status)
    .bind(work_item_id)
    .bind(tenant_id)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn get_work_item_detail(
    pool: &SqlitePool,
    tenant_id: i64,
    work_item_id: i64,
) -> Result<Option<(WorkItem, Vec<ActionRecommendation>, Option<RationaleCard>, Vec<Evidence>)>, sqlx::Error> {
    let work_item = sqlx::query_as::<_, WorkItem>(
        "SELECT * FROM companion_autonomy_work_items WHERE tenant_id = ? AND id = ?"
    )
    .bind(tenant_id)
    .bind(work_item_id)
    .fetch_optional(pool)
    .await?;

    let work_item = match work_item {
        Some(item) => item,
        None => return Ok(None),
    };

    let actions = sqlx::query_as::<_, ActionRecommendation>(
        "SELECT * FROM companion_autonomy_action_recommendations WHERE work_item_id = ?"
    )
    .bind(work_item_id)
    .fetch_all(pool)
    .await?;

    let rationale = sqlx::query_as::<_, RationaleCard>(
        "SELECT * FROM companion_autonomy_rationale_cards WHERE work_item_id = ? ORDER BY version DESC LIMIT 1"
    )
    .bind(work_item_id)
    .fetch_optional(pool)
    .await?;

    let evidence = sqlx::query_as::<_, Evidence>(
        "SELECT * FROM companion_autonomy_evidence WHERE work_item_id = ?"
    )
    .bind(work_item_id)
    .fetch_all(pool)
    .await?;

    Ok(Some((work_item, actions, rationale, evidence)))
}

pub async fn action_work_item_id(
    pool: &SqlitePool,
    tenant_id: i64,
    action_id: i64,
) -> Result<Option<i64>, sqlx::Error> {
    sqlx::query_scalar(
        "SELECT work_item_id FROM companion_autonomy_action_recommendations
         WHERE tenant_id = ? AND id = ?"
    )
    .bind(tenant_id)
    .bind(action_id)
    .fetch_optional(pool)
    .await
}

pub async fn action_work_item_ids(
    pool: &SqlitePool,
    tenant_id: i64,
    action_ids: &[i64],
) -> Result<Vec<(i64, i64)>, sqlx::Error> {
    let mut pairs = Vec::new();
    for action_id in action_ids {
        if let Some(work_item_id) = action_work_item_id(pool, tenant_id, *action_id).await? {
            pairs.push((*action_id, work_item_id));
        }
    }
    Ok(pairs)
}

pub async fn action_for_work_item(
    pool: &SqlitePool,
    tenant_id: i64,
    work_item_id: i64,
) -> Result<Option<ActionRecommendation>, sqlx::Error> {
    sqlx::query_as::<_, ActionRecommendation>(
        "SELECT * FROM companion_autonomy_action_recommendations
         WHERE tenant_id = ? AND work_item_id = ?
         ORDER BY CASE action_kind WHEN 'apply' THEN 0 WHEN 'review' THEN 1 ELSE 2 END
         LIMIT 1"
    )
    .bind(tenant_id)
    .bind(work_item_id)
    .fetch_optional(pool)
    .await
}

pub async fn list_work_items_by_status(
    pool: &SqlitePool,
    tenant_id: i64,
    statuses: &[&str],
    limit: i64,
) -> Result<Vec<WorkItem>, sqlx::Error> {
    if statuses.is_empty() {
        return Ok(Vec::new());
    }
    let placeholders = std::iter::repeat("?").take(statuses.len()).collect::<Vec<_>>().join(",");
    let query = format!(
        "SELECT * FROM companion_autonomy_work_items
         WHERE tenant_id = ? AND status IN ({})
         ORDER BY priority DESC, created_at DESC
         LIMIT ?",
        placeholders
    );
    let mut q = sqlx::query_as::<_, WorkItem>(&query).bind(tenant_id);
    for status in statuses {
        q = q.bind(*status);
    }
    q.bind(limit).fetch_all(pool).await
}

pub async fn work_item_by_dedupe_key(
    pool: &SqlitePool,
    tenant_id: i64,
    dedupe_key: &str,
) -> Result<Option<WorkItem>, sqlx::Error> {
    sqlx::query_as::<_, WorkItem>(
        "SELECT * FROM companion_autonomy_work_items WHERE tenant_id = ? AND dedupe_key = ?"
    )
    .bind(tenant_id)
    .bind(dedupe_key)
    .fetch_optional(pool)
    .await
}

pub async fn work_item_by_id(
    pool: &SqlitePool,
    tenant_id: i64,
    work_item_id: i64,
) -> Result<Option<WorkItem>, sqlx::Error> {
    sqlx::query_as::<_, WorkItem>(
        "SELECT * FROM companion_autonomy_work_items WHERE tenant_id = ? AND id = ?"
    )
    .bind(tenant_id)
    .bind(work_item_id)
    .fetch_optional(pool)
    .await
}

pub async fn update_work_item_status_by_dedupe_key(
    pool: &SqlitePool,
    tenant_id: i64,
    dedupe_key: &str,
    status: &str,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE companion_autonomy_work_items
         SET status = ?, updated_at = datetime('now')
         WHERE tenant_id = ? AND dedupe_key = ?"
    )
    .bind(status)
    .bind(tenant_id)
    .bind(dedupe_key)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}
