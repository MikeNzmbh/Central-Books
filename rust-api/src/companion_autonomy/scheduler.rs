use serde_json::json;
use sqlx::SqlitePool;

use crate::companion_autonomy::agents::{self, AgentContext, AgentName};
use crate::companion_autonomy::copy::customer_safe_copy;
use crate::companion_autonomy::models::{AgentOutput, RecommendationSeed, WorkItemSeed};
use crate::companion_autonomy::policy::{BudgetConfig, PolicyConfig};
use crate::companion_autonomy::tool_gateway::ToolGateway;
use crate::companion_autonomy::{hash_inputs, store};

pub async fn tick(pool: &SqlitePool, tenant_ids: Vec<i64>, actor_id: Option<i64>) -> Result<(), String> {
    for tenant_id in tenant_ids {
        if let Ok(Some(enabled)) = store::business_ai_enabled(pool, tenant_id).await {
            if !enabled {
                continue;
            }
        }
        if let Ok(Some(settings)) = store::fetch_ai_settings(pool, tenant_id).await {
            if !settings.ai_enabled || settings.kill_switch {
                continue;
            }
        }
        let ctx = build_context(pool, tenant_id)?;
        ensure_policy_row(pool, tenant_id, &ctx).await?;

        let mut output = AgentOutput::empty();
        let reconciliation_output = run_agent_job(&ctx, AgentName::Reconciliation).await?;
        merge_output(&mut output, reconciliation_output);

        let categorization_output = run_agent_job(&ctx, AgentName::Categorization).await?;
        merge_output(&mut output, categorization_output);

        let narrative_job_id = store::insert_job(
            pool,
            ctx.tenant_id,
            "NarrativeAgent",
            "succeeded",
            30,
            &serde_json::json!({"status": "generated"}),
            &budget_json(),
        )
        .await
        .map_err(|e| e.to_string())?;
        let _ = store::update_job_status(pool, &narrative_job_id, "succeeded", None, None).await;

        let work_item_count = output.work_items.len() as i64;
        if work_item_count > ctx.policy.velocity_threshold {
            let _ = store::insert_breaker_event(
                pool,
                ctx.tenant_id,
                ctx.business_id,
                "velocity",
                ctx.policy.velocity_threshold as f64,
                work_item_count as f64,
                "require_approval",
                None,
            )
            .await;
        }
        apply_agent_output(pool, &output).await?;
        let _ = store::insert_audit_log(
            pool,
            ctx.tenant_id,
            ctx.business_id,
            actor_id,
            if actor_id.is_some() { "user" } else { "system" },
            "engine_tick",
            "companion_autonomy",
            &format!("tenant:{}", ctx.tenant_id),
            &serde_json::json!({ "work_items": work_item_count }),
        )
        .await;
    }
    Ok(())
}

pub async fn materialize(
    pool: &SqlitePool,
    tenant_ids: Vec<i64>,
    stale_minutes: i64,
    actor_id: Option<i64>,
) -> Result<(), String> {
    for tenant_id in tenant_ids {
        let payload = store::fetch_cockpit_queues(pool, tenant_id)
            .await
            .map_err(|e| e.to_string())?;
        let business_id = tenant_id;
        store::insert_snapshot(
            pool,
            tenant_id,
            business_id,
            &serde_json::to_value(&payload).unwrap_or_else(|_| json!({})),
            stale_minutes,
            "v1",
        )
        .await
        .map_err(|e| e.to_string())?;
        let _ = store::insert_queue_snapshot(
            pool,
            tenant_id,
            &serde_json::to_value(&payload).unwrap_or_else(|_| json!({})),
            stale_minutes.saturating_mul(60),
        )
        .await;
        let _ = store::insert_audit_log(
            pool,
            tenant_id,
            business_id,
            actor_id,
            if actor_id.is_some() { "user" } else { "system" },
            "engine_materialize",
            "companion_autonomy",
            &format!("tenant:{}", tenant_id),
            &serde_json::json!({ "snapshot": "queue" }),
        )
        .await;
    }
    Ok(())
}

pub async fn run_agent_for_work_item(
    pool: &SqlitePool,
    tenant_id: i64,
    agent_name: AgentName,
    work_item_id: i64,
) -> Result<(), String> {
    if let Ok(Some(settings)) = store::fetch_ai_settings(pool, tenant_id).await {
        if !settings.ai_enabled || settings.kill_switch {
            return Ok(());
        }
    }
    let ctx = build_context(pool, tenant_id)?;
    ensure_policy_row(pool, tenant_id, &ctx).await?;
    let output = run_agent_with_record(&ctx, agent_name, Some(work_item_id)).await?;
    apply_agent_output(pool, &output).await?;
    Ok(())
}

pub async fn run_agent_for_tenant(
    pool: &SqlitePool,
    tenant_id: i64,
    agent_name: AgentName,
) -> Result<(), String> {
    if let Ok(Some(settings)) = store::fetch_ai_settings(pool, tenant_id).await {
        if !settings.ai_enabled || settings.kill_switch {
            return Ok(());
        }
    }
    let ctx = build_context(pool, tenant_id)?;
    ensure_policy_row(pool, tenant_id, &ctx).await?;
    let output = run_agent_with_record(&ctx, agent_name, None).await?;
    apply_agent_output(pool, &output).await?;
    Ok(())
}

pub async fn run_worker(pool: &SqlitePool, once: bool, limit: i64) -> Result<(), String> {
    loop {
        let runs = fetch_queued_runs(pool, limit).await.map_err(|e| e.to_string())?;
        if runs.is_empty() {
            if once {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_secs(5)).await;
            continue;
        }

        for (run_id, tenant_id, agent_name) in runs {
            if let Ok(Some(settings)) = store::fetch_ai_settings(pool, tenant_id).await {
                if !settings.ai_enabled || settings.kill_switch {
                    continue;
                }
            }
            let ctx = build_context(pool, tenant_id)?;
            ensure_policy_row(pool, tenant_id, &ctx).await?;
            if let Some(agent) = agent_from_str(&agent_name) {
                store::mark_agent_run_started(pool, run_id)
                    .await
                    .map_err(|e| e.to_string())?;
                match agents::run_agent(agent, &ctx).await {
                    Ok(output) => {
                        let outputs_json = serde_json::to_value(&output).unwrap_or_else(|_| json!({}));
                        store::complete_agent_run(pool, run_id, &outputs_json)
                            .await
                            .map_err(|e| e.to_string())?;
                        apply_agent_output(pool, &output).await?;
                    }
                    Err(err) => {
                        store::fail_agent_run(pool, run_id, "agent_error", &err)
                            .await
                            .map_err(|e| e.to_string())?;
                    }
                }
            } else {
                store::fail_agent_run(pool, run_id, "unknown_agent", "Unknown agent name")
                    .await
                    .map_err(|e| e.to_string())?;
            }
        }

        if once {
            break;
        }
    }
    Ok(())
}

fn build_context(pool: &SqlitePool, tenant_id: i64) -> Result<AgentContext, String> {
    let policy = PolicyConfig::from_env();
    let tool_gateway = ToolGateway::new(pool.clone());
    Ok(AgentContext {
        pool: pool.clone(),
        tenant_id,
        business_id: tenant_id,
        policy,
        tool_gateway,
    })
}

async fn run_agent_job(ctx: &AgentContext, agent_name: AgentName) -> Result<AgentOutput, String> {
    let job_id = store::insert_job(
        &ctx.pool,
        ctx.tenant_id,
        agent_name.as_str(),
        "queued",
        50,
        &serde_json::json!({ "agent": agent_name.as_str() }),
        &budget_json(),
    )
    .await
    .map_err(|e| e.to_string())?;
    let _ = store::update_job_status(&ctx.pool, &job_id, "running", None, None).await;

    match run_agent_with_record(ctx, agent_name, None).await {
        Ok(output) => {
            let outputs_json = serde_json::to_value(&output).unwrap_or_else(|_| json!({}));
            let _ = store::update_job_status(&ctx.pool, &job_id, "succeeded", Some(&outputs_json), None).await;
            Ok(output)
        }
        Err(err) => {
            let _ = store::update_job_status(&ctx.pool, &job_id, "failed", None, Some(&err)).await;
            Err(err)
        }
    }
}

fn merge_output(target: &mut AgentOutput, other: AgentOutput) {
    target.signals.extend(other.signals);
    target.recommendations.extend(other.recommendations);
    target.evidence_refs.extend(other.evidence_refs);
    target.work_items.extend(other.work_items);
}

async fn ensure_policy_row(pool: &SqlitePool, tenant_id: i64, ctx: &AgentContext) -> Result<(), String> {
    if store::fetch_policy(pool, tenant_id)
        .await
        .map_err(|e| e.to_string())?
        .is_some()
    {
        return Ok(());
    }
    let breaker_thresholds = json!({
        "approval_amount_threshold": ctx.policy.approval_amount_threshold,
        "velocity_threshold": ctx.policy.velocity_threshold
    });
    let allowlists = json!({
        "domains": ctx.tool_gateway.allowed_domains.clone(),
        "models": ctx.tool_gateway.allowed_models.clone()
    });
    let budget = BudgetConfig::from_env();
    let budgets = json!({
        "tokens_per_day": budget.tokens_per_day,
        "tool_calls_per_day": budget.tool_calls_per_day,
        "runs_per_day": budget.runs_per_day
    });
    store::upsert_policy(
        pool,
        tenant_id,
        "suggest_only",
        &breaker_thresholds,
        &allowlists,
        &budgets,
    )
    .await
    .map_err(|e| e.to_string())
}

fn budget_json() -> serde_json::Value {
    let budget = BudgetConfig::from_env();
    json!({
        "tokens_per_day": budget.tokens_per_day,
        "tool_calls_per_day": budget.tool_calls_per_day,
        "runs_per_day": budget.runs_per_day
    })
}
async fn run_agent_with_record(
    ctx: &AgentContext,
    agent_name: AgentName,
    work_item_id: Option<i64>,
) -> Result<AgentOutput, String> {
    let input_payload = json!({
        "agent": agent_name.as_str(),
        "tenant_id": ctx.tenant_id,
        "work_item_id": work_item_id,
    });
    let inputs_hash = hash_inputs(&input_payload.to_string());
    let run_id = store::insert_agent_run(
        &ctx.pool,
        ctx.tenant_id,
        ctx.business_id,
        work_item_id,
        agent_name.as_str(),
        &inputs_hash,
        4000,
        6,
        45,
    )
    .await
    .map_err(|e| e.to_string())?;

    store::mark_agent_run_started(&ctx.pool, run_id)
        .await
        .map_err(|e| e.to_string())?;

    let output = agents::run_agent(agent_name, ctx).await;
    match &output {
        Ok(out) => {
            let outputs_json = serde_json::to_value(out).unwrap_or_else(|_| json!({}));
            store::complete_agent_run(&ctx.pool, run_id, &outputs_json)
                .await
                .map_err(|e| e.to_string())?;
        }
        Err(err) => {
            store::fail_agent_run(&ctx.pool, run_id, "agent_error", err)
                .await
                .map_err(|e| e.to_string())?;
        }
    }

    output
}

pub async fn apply_agent_output(
    pool: &SqlitePool,
    output: &AgentOutput,
) -> Result<(), String> {
    for seed in &output.work_items {
        let mut seed = seed.clone();
        if seed.requires_approval && seed.status == "open" {
            seed.status = "waiting_approval".to_string();
        }

        let work_item = store::upsert_work_item(pool, &seed)
            .await
            .map_err(|e| e.to_string())?;

        let recommendations = default_recommendations(&seed);
        for rec in &recommendations {
            store::upsert_action_recommendation(
                pool,
                work_item.id,
                rec,
                seed.tenant_id,
                seed.business_id,
            )
            .await
            .map_err(|e| e.to_string())?;
        }

        let evidence_refs = seed_evidence_refs(&seed);
        let (sections, customer_safe_text) = agents::narrative::build_card(
            &seed,
            &recommendations,
            &output.signals,
            &evidence_refs,
        );
        store::insert_rationale_card(
            pool,
            work_item.id,
            seed.tenant_id,
            seed.business_id,
            &sections,
            &customer_safe_text,
        )
        .await
        .map_err(|e| e.to_string())?;

        let claim_id = store::insert_claim(
            pool,
            seed.tenant_id,
            seed.business_id,
            work_item.id,
            &customer_safe_copy(&seed.internal_title),
            seed.confidence_score,
            "unverified",
            0.6,
        )
        .await
        .map_err(|e| e.to_string())?;

        for evidence_ref in &evidence_refs {
            let url = format!("internal://{}", evidence_ref);
            let evidence_id = store::insert_evidence(
                pool,
                seed.tenant_id,
                seed.business_id,
                work_item.id,
                &url,
                "System record",
                evidence_ref,
                "allowlisted",
            )
            .await
            .map_err(|e| e.to_string())?;
            store::link_claim_evidence(pool, claim_id, evidence_id)
                .await
                .map_err(|e| e.to_string())?;
        }

        store::insert_audit_log(
            pool,
            seed.tenant_id,
            seed.business_id,
            None,
            "system",
            "work_item.upsert",
            "work_item",
            &work_item.id.to_string(),
            &json!({"dedupe_key": seed.dedupe_key, "status": seed.status}),
        )
        .await
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn default_recommendations(seed: &WorkItemSeed) -> Vec<RecommendationSeed> {
    let (action_kind, requires_confirm) = if seed.risk_level == "low" && !seed.requires_approval {
        ("apply", false)
    } else {
        ("review", true)
    };

    vec![RecommendationSeed {
        action_kind: action_kind.to_string(),
        payload: json!({"work_item": seed.dedupe_key}),
        preview_effects: json!({
            "title": seed.customer_title,
            "summary": seed.customer_summary,
        }),
        status: "proposed".to_string(),
        requires_confirm,
    }]
}

fn seed_evidence_refs(seed: &WorkItemSeed) -> Vec<String> {
    let mut refs = Vec::new();
    if let Some(id) = seed.inputs.get("transaction_id").and_then(|v| v.as_i64()) {
        refs.push(format!("bank_transaction:{}", id));
    }
    if let Some(id) = seed.inputs.get("receipt_document_id").and_then(|v| v.as_i64()) {
        refs.push(format!("receipt_document:{}", id));
    }
    if let Some(id) = seed.inputs.get("invoice_document_id").and_then(|v| v.as_i64()) {
        refs.push(format!("invoice_document:{}", id));
    }
    if let Some(id) = seed.inputs.get("document_id").and_then(|v| v.as_i64()) {
        refs.push(format!("document:{}", id));
    }
    refs
}

async fn fetch_queued_runs(pool: &SqlitePool, limit: i64) -> Result<Vec<(i64, i64, String)>, sqlx::Error> {
    sqlx::query_as(
        "SELECT id, tenant_id, agent_name
         FROM companion_autonomy_agent_runs
         WHERE status = 'queued'
         ORDER BY created_at ASC
         LIMIT ?"
    )
    .bind(limit)
    .fetch_all(pool)
    .await
}

fn agent_from_str(name: &str) -> Option<AgentName> {
    match name {
        "OrchestratorAgent" => Some(AgentName::Orchestrator),
        "CategorizationAgent" => Some(AgentName::Categorization),
        "ReconciliationAgent" => Some(AgentName::Reconciliation),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_autonomy::schema;

    async fn seed_core_bank_data(pool: &SqlitePool, tenant_id: i64) {
        sqlx::query(
            "CREATE TABLE core_bankaccount (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL
            )"
        )
        .execute(pool)
        .await
        .unwrap();

        sqlx::query(
            "CREATE TABLE core_banktransaction (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_account_id INTEGER NOT NULL,
                description TEXT,
                amount REAL,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                category_id INTEGER
            )"
        )
        .execute(pool)
        .await
        .unwrap();

        sqlx::query("INSERT INTO core_bankaccount (id, business_id) VALUES (?, ?)")
            .bind(1)
            .bind(tenant_id)
            .execute(pool)
            .await
            .unwrap();

        sqlx::query(
            "INSERT INTO core_banktransaction (bank_account_id, description, amount, date, status, category_id)
             VALUES (?, ?, ?, ?, ?, NULL)"
        )
        .bind(1)
        .bind("Test transaction")
        .bind(120.0)
        .bind("2025-01-10")
        .bind("NEW")
        .execute(pool)
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn tick_enqueues_jobs() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();
        seed_core_bank_data(&pool, 1).await;

        tick(&pool, vec![1], None).await.unwrap();

        let job_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM companion_autonomy_jobs WHERE tenant_id = ?"
        )
        .bind(1)
        .fetch_one(&pool)
        .await
        .unwrap();
        let work_item_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM companion_autonomy_work_items WHERE tenant_id = ?"
        )
        .bind(1)
        .fetch_one(&pool)
        .await
        .unwrap();

        assert!(job_count >= 2);
        assert!(work_item_count >= 1);
    }

    #[tokio::test]
    async fn materialize_creates_snapshot() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();
        seed_core_bank_data(&pool, 1).await;
        tick(&pool, vec![1], None).await.unwrap();

        materialize(&pool, vec![1], 10, None).await.unwrap();

        let snapshot_count: i64 = sqlx::query_scalar(
            "SELECT COUNT(*) FROM companion_autonomy_queue_snapshot WHERE tenant_id = ?"
        )
        .bind(1)
        .fetch_one(&pool)
        .await
        .unwrap();
        assert_eq!(snapshot_count, 1);
    }
}
