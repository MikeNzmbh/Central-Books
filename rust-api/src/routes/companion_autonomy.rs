use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use chrono::TimeZone;
use serde::Deserialize;
use serde_json::{json, Value};

use crate::companion_autonomy::{policy::BudgetConfig, store};
use crate::routes::auth::{extract_claims_from_header, Claims};
use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct TenantQuery {
    pub business_id: Option<i64>,
    pub tenant_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct SnoozePayload {
    pub until: String,
}

#[derive(Debug, Deserialize)]
pub struct DismissPayload {
    pub note: Option<String>,
    pub reason_code: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ApprovalRequestPayload {
    pub reason_required: Option<bool>,
    pub reason_text: Option<String>,
    pub expires_at: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ApprovalDecisionPayload {
    pub reason_text: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct BatchApplyPayload {
    pub action_ids: Vec<i64>,
}

#[derive(Debug, Deserialize)]
pub struct EngineRunPayload {
    pub tenant: Option<String>,
    pub tenant_id: Option<i64>,
    pub max_age_minutes: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct PolicyUpdatePayload {
    pub mode: String,
    pub breaker_thresholds: Option<Value>,
    pub allowlists: Option<Value>,
    pub budgets: Option<Value>,
}

pub async fn autonomy_status(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<TenantQuery>,
) -> impl axum::response::IntoResponse {
    let claims = match require_claims(&headers) {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let tenant_id = match claims.business_id {
        Some(id) => id,
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(json!({ "ok": false, "error": "unauthorized" })),
            );
        }
    };
    let queues = store::fetch_cockpit_queues(&state.db, tenant_id)
        .await
        .unwrap_or_else(|_| {
            crate::companion_autonomy::models::CockpitQueues {
                generated_at: crate::companion_autonomy::now_utc_str(),
                mode: "suggest_only".to_string(),
                trust_score: 0.0,
                stats: serde_json::json!({}),
                ready_queue: vec![],
                needs_attention_queue: vec![],
                job_totals: None,
                job_by_agent: None,
                top_blockers: None,
            }
        });

    let usage = store::tool_usage_last_day(&state.db, tenant_id)
        .await
        .unwrap_or((0, 0));
    let budget = BudgetConfig::from_env();
    let breakers = store::breaker_events_last_day(&state.db, tenant_id).await.unwrap_or(0);

    (
        StatusCode::OK,
        Json(serde_json::json!({
        "ok": true,
        "mode": queues.mode,
        "trust_score": queues.trust_score,
        "stats": queues.stats,
        "budgets": {
            "tokens_per_day": budget.tokens_per_day,
            "tool_calls_per_day": budget.tool_calls_per_day,
            "runs_per_day": budget.runs_per_day
        },
        "usage": {
            "tool_calls_last_day": usage.0,
            "tokens_last_day": usage.1
        },
        "breaker_events_last_day": breakers
    })),
    )
}

pub async fn cockpit_status(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<TenantQuery>,
) -> impl axum::response::IntoResponse {
    let claims = match require_claims(&headers) {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let tenant_id = match claims.business_id {
        Some(id) => id,
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(json!({ "ok": false, "error": "unauthorized" })),
            );
        }
    };

    let policy_mode = store::fetch_policy(&state.db, tenant_id)
        .await
        .ok()
        .flatten()
        .map(|row| row.mode)
        .unwrap_or_else(|| "suggest_only".to_string());
    let breakers = store::breaker_events_last_day(&state.db, tenant_id).await.unwrap_or(0);
    let budget = BudgetConfig::from_env();
    let last_tick_at = store::latest_audit_action_time(&state.db, tenant_id, "engine_tick")
        .await
        .ok()
        .flatten();
    let last_materialized_at = store::latest_audit_action_time(&state.db, tenant_id, "engine_materialize")
        .await
        .ok()
        .flatten();

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "tenant_id": tenant_id,
            "mode": policy_mode,
            "breakers": {
                "recent": breakers,
                "ok": breakers == 0
            },
            "budgets": {
                "tokens_per_day": budget.tokens_per_day,
                "tool_calls_per_day": budget.tool_calls_per_day,
                "runs_per_day": budget.runs_per_day
            },
            "last_tick_at": last_tick_at,
            "last_materialized_at": last_materialized_at,
            "engine_version": "v1",
            "mock_mode": {
                "llm": std::env::var("LLM_MODE").unwrap_or_else(|_| "live".to_string()),
                "tools": std::env::var("TOOL_MODE").unwrap_or_else(|_| "live".to_string())
            }
        })),
    )
}

pub async fn cockpit_queues(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<TenantQuery>,
) -> impl axum::response::IntoResponse {
    let claims = match require_claims(&headers) {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let tenant_id = match claims.business_id {
        Some(id) => id,
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(json!({ "ok": false, "error": "unauthorized" })),
            );
        }
    };
    if let Ok(Some(snapshot)) = store::latest_queue_snapshot(&state.db, tenant_id).await {
        let payload: serde_json::Value =
            serde_json::from_str(&snapshot.snapshot_json).unwrap_or_else(|_| serde_json::json!({}));
        let stale = is_queue_snapshot_stale(&snapshot.generated_at, snapshot.stale_after_seconds);
        return (
            StatusCode::OK,
            Json(serde_json::json!({
                "ok": true,
                "source": "snapshot",
                "stale": stale,
                "data": payload
            })),
        );
    }

    let queues = store::fetch_cockpit_queues(&state.db, tenant_id)
        .await
        .unwrap_or_else(|_| {
            crate::companion_autonomy::models::CockpitQueues {
                generated_at: crate::companion_autonomy::now_utc_str(),
                mode: "suggest_only".to_string(),
                trust_score: 0.0,
                stats: serde_json::json!({}),
                ready_queue: vec![],
                needs_attention_queue: vec![],
                job_totals: None,
                job_by_agent: None,
                top_blockers: None,
            }
        });

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "source": "live",
            "stale": false,
            "data": queues
        })),
    )
}

pub async fn engine_tick(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<TenantQuery>,
    Json(payload): Json<EngineRunPayload>,
) -> impl axum::response::IntoResponse {
    let claims = match require_staff(&state, &headers).await {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let tenant_id = resolve_tenant_id_from_payload(&headers, &payload, params.business_id, params.tenant_id);
    let tenants = if payload.tenant.as_deref() == Some("all") {
        store::list_business_ids(&state.db).await.unwrap_or_else(|_| vec![tenant_id])
    } else {
        vec![tenant_id]
    };
    match crate::companion_autonomy::scheduler::tick(&state.db, tenants, claims.sub.parse::<i64>().ok()).await {
        Ok(_) => (
            StatusCode::OK,
            Json(serde_json::json!({ "ok": true })),
        ),
        Err(err) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "ok": false, "error": err })),
        ),
    }
}

pub async fn engine_materialize(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<TenantQuery>,
    Json(payload): Json<EngineRunPayload>,
) -> impl axum::response::IntoResponse {
    let claims = match require_staff(&state, &headers).await {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let tenant_id = resolve_tenant_id_from_payload(&headers, &payload, params.business_id, params.tenant_id);
    let tenants = if payload.tenant.as_deref() == Some("all") {
        store::list_business_ids(&state.db).await.unwrap_or_else(|_| vec![tenant_id])
    } else {
        vec![tenant_id]
    };
    let stale = payload
        .max_age_minutes
        .unwrap_or_else(|| crate::companion_autonomy::policy::PolicyConfig::from_env().snapshot_stale_minutes);
    match crate::companion_autonomy::scheduler::materialize(&state.db, tenants, stale, claims.sub.parse::<i64>().ok()).await {
        Ok(_) => (
            StatusCode::OK,
            Json(serde_json::json!({ "ok": true })),
        ),
        Err(err) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "ok": false, "error": err })),
        ),
    }
}

pub async fn update_policy(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<TenantQuery>,
    Json(payload): Json<PolicyUpdatePayload>,
) -> impl axum::response::IntoResponse {
    let _claims = match require_staff(&state, &headers).await {
        Ok(claims) => claims,
        Err(response) => return response,
    };
    let tenant_id = resolve_tenant_id(&headers, params.business_id.or(params.tenant_id));
    let breaker_thresholds = payload
        .breaker_thresholds
        .unwrap_or_else(|| serde_json::json!({}));
    let allowlists = payload
        .allowlists
        .unwrap_or_else(|| serde_json::json!({}));
    let budgets = payload
        .budgets
        .unwrap_or_else(|| serde_json::json!({}));
    let result = store::upsert_policy(
        &state.db,
        tenant_id,
        &payload.mode,
        &breaker_thresholds,
        &allowlists,
        &budgets,
    )
    .await;
    match result {
        Ok(_) => (
            StatusCode::OK,
            Json(serde_json::json!({ "ok": true })),
        ),
        Err(err) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "ok": false, "error": err.to_string() })),
        ),
    }
}

pub async fn list_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<TenantQuery>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let runs = store::list_agent_runs(&state.db, tenant_id, 50)
        .await
        .unwrap_or_default();
    (
        StatusCode::OK,
        Json(serde_json::json!({
        "ok": true,
        "runs": runs
        })),
    )
}

pub async fn work_detail(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(work_item_id): Path<i64>,
    Query(_params): Query<TenantQuery>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let detail = store::get_work_item_detail(&state.db, tenant_id, work_item_id)
        .await
        .unwrap_or(None);

    if let Some((work_item, actions, rationale, evidence)) = detail {
        let inputs: serde_json::Value = serde_json::from_str(&work_item.inputs_json).unwrap_or_default();
        let state_json: serde_json::Value = serde_json::from_str(&work_item.state_json).unwrap_or_default();
        let links: serde_json::Value = serde_json::from_str(&work_item.links_json).unwrap_or_default();
        let actions_json: Vec<serde_json::Value> = actions
            .into_iter()
            .map(|action| {
                let payload: serde_json::Value =
                    serde_json::from_str(&action.payload_json).unwrap_or_default();
                let preview: serde_json::Value =
                    serde_json::from_str(&action.preview_effects_json).unwrap_or_default();
                serde_json::json!({
                    "id": action.id,
                    "action_kind": action.action_kind,
                    "status": action.status,
                    "requires_confirm": action.requires_confirm,
                    "payload": payload,
                    "preview_effects": preview
                })
            })
            .collect();

        let rationale_json = rationale.map(|card| {
            serde_json::json!({
                "sections": serde_json::from_str::<serde_json::Value>(&card.sections_json).unwrap_or_default(),
                "customer_safe_text": card.customer_safe_text,
                "generated_at": card.generated_at,
                "version": card.version
            })
        });

        return (
            StatusCode::OK,
            Json(serde_json::json!({
            "ok": true,
            "work_item": {
                "id": work_item.id,
                "type": work_item.work_type,
                "surface": work_item.surface,
                "status": work_item.status,
                "priority": work_item.priority,
                "risk_level": work_item.risk_level,
                "confidence_score": work_item.confidence_score,
                "requires_approval": work_item.requires_approval,
                "customer_title": work_item.customer_title,
                "customer_summary": work_item.customer_summary,
                "inputs": inputs,
                "state": state_json,
                "links": links
            },
            "recommendations": actions_json,
            "rationale": rationale_json,
            "evidence": evidence
            })),
        );
    }

    (
        StatusCode::NOT_FOUND,
        Json(serde_json::json!({"ok": false, "error": "work item not found"})),
    )
}

pub async fn dismiss_work_item(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(work_item_id): Path<i64>,
    Query(_params): Query<TenantQuery>,
    Json(payload): Json<DismissPayload>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let actor_id = require_user_id(&headers).ok();
    let dismissed = store::dismiss_work_item(&state.db, tenant_id, work_item_id)
        .await
        .unwrap_or(false);

    let _ = store::insert_audit_log(
        &state.db,
        tenant_id,
        tenant_id,
        actor_id,
        "user",
        "work_item.dismiss",
        "work_item",
        &work_item_id.to_string(),
        &serde_json::json!({
            "note": payload.note,
            "reason_code": payload.reason_code
        }),
    )
    .await;

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "dismissed": dismissed
        })),
    )
}

pub async fn snooze_work_item(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(work_item_id): Path<i64>,
    Query(_params): Query<TenantQuery>,
    Json(payload): Json<SnoozePayload>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let snoozed = store::snooze_work_item(&state.db, tenant_id, work_item_id, &payload.until)
        .await
        .unwrap_or(false);

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "snoozed": snoozed
        })),
    )
}

pub async fn request_approval(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(work_item_id): Path<i64>,
    Query(_params): Query<TenantQuery>,
    Json(payload): Json<ApprovalRequestPayload>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let request = store::create_approval_request(
        &state.db,
        tenant_id,
        tenant_id,
        work_item_id,
        &format!("user:{}", actor_id),
        payload.reason_required.unwrap_or(false),
        payload.reason_text.as_deref(),
        payload.expires_at.as_deref(),
    )
    .await;

    if let Ok(request) = request {
        let _ = store::update_work_item_status(&state.db, work_item_id, tenant_id, "waiting_approval").await;
        return (
            StatusCode::OK,
            Json(serde_json::json!({
                "ok": true,
                "approval": request
            })),
        );
    }

    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(serde_json::json!({"ok": false, "error": "failed to create approval"})),
    )
}

pub async fn approve_request(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(approval_id): Path<i64>,
    Json(payload): Json<ApprovalDecisionPayload>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let updated = store::set_approval_status(
        &state.db,
        tenant_id,
        approval_id,
        "approved",
        Some(actor_id),
        payload.reason_text.as_deref(),
    )
    .await
    .unwrap_or(false);

    if updated {
        if let Ok(Some((tenant_id, work_item_id))) = fetch_approval_work_item(&state.db, approval_id, tenant_id).await {
            let _ = store::update_work_item_status(&state.db, work_item_id, tenant_id, "ready").await;
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "approved": updated
        })),
    )
}

pub async fn reject_request(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(approval_id): Path<i64>,
    Json(payload): Json<ApprovalDecisionPayload>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let actor_id = match require_user_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };

    let updated = store::set_approval_status(
        &state.db,
        tenant_id,
        approval_id,
        "rejected",
        Some(actor_id),
        payload.reason_text.as_deref(),
    )
    .await
    .unwrap_or(false);

    if updated {
        if let Ok(Some((tenant_id, work_item_id))) = fetch_approval_work_item(&state.db, approval_id, tenant_id).await {
            let _ = store::update_work_item_status(&state.db, work_item_id, tenant_id, "dismissed").await;
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "rejected": updated
        })),
    )
}

pub async fn apply_action(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(action_id): Path<i64>,
    Query(_params): Query<TenantQuery>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    if !can_apply_action(&state.db, tenant_id, action_id).await.unwrap_or(false) {
        return (
            StatusCode::FORBIDDEN,
            Json(serde_json::json!({
                "ok": false,
                "error": "approval required"
            })),
        );
    }

    let applied = store::apply_action(&state.db, tenant_id, action_id)
        .await
        .unwrap_or(false);

    if applied {
        if let Ok(Some(work_item_id)) = store::action_work_item_id(&state.db, tenant_id, action_id).await {
            let _ = store::update_work_item_status(&state.db, work_item_id, tenant_id, "applied").await;
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "applied": applied
        })),
    )
}

pub async fn batch_apply_actions(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(_params): Query<TenantQuery>,
    Json(payload): Json<BatchApplyPayload>,
) -> impl axum::response::IntoResponse {
    let tenant_id = match require_business_id(&headers) {
        Ok(id) => id,
        Err(response) => return response,
    };
    let mut results = Vec::new();
    let mut applied_ids = Vec::new();
    for action_id in &payload.action_ids {
        let allowed = can_apply_action(&state.db, tenant_id, *action_id).await.unwrap_or(false);
        if allowed {
            let applied = store::apply_action(&state.db, tenant_id, *action_id)
                .await
                .unwrap_or(false);
            if applied {
                applied_ids.push(*action_id);
            }
            results.push(serde_json::json!({
                "action_id": action_id,
                "applied": applied
            }));
        } else {
            results.push(serde_json::json!({
                "action_id": action_id,
                "applied": false,
                "reason": "approval required"
            }));
        }
    }

    let work_item_pairs = store::action_work_item_ids(&state.db, tenant_id, &applied_ids)
        .await
        .unwrap_or_default();
    for (_, work_item_id) in work_item_pairs {
        let _ = store::update_work_item_status(&state.db, work_item_id, tenant_id, "applied").await;
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok": true,
            "results": results
        })),
    )
}

fn resolve_tenant_id(headers: &HeaderMap, fallback: Option<i64>) -> i64 {
    if let Ok(claims) = extract_claims_from_header(headers) {
        if let Some(business_id) = claims.business_id {
            return business_id;
        }
    }
    fallback.unwrap_or(1)
}

fn resolve_tenant_id_from_payload(
    headers: &HeaderMap,
    payload: &EngineRunPayload,
    business_id: Option<i64>,
    tenant_id: Option<i64>,
) -> i64 {
    resolve_tenant_id(headers, payload.tenant_id.or(tenant_id).or(business_id))
}

fn require_claims(headers: &HeaderMap) -> Result<Claims, (StatusCode, Json<serde_json::Value>)> {
    extract_claims_from_header(headers)
        .map_err(|_| (StatusCode::UNAUTHORIZED, Json(json!({ "ok": false, "error": "unauthorized" }))))
}

fn require_business_id(headers: &HeaderMap) -> Result<i64, (StatusCode, Json<serde_json::Value>)> {
    require_claims(headers)?
        .business_id
        .ok_or_else(|| (StatusCode::UNAUTHORIZED, Json(json!({ "ok": false, "error": "unauthorized" }))))
}

fn require_user_id(headers: &HeaderMap) -> Result<i64, (StatusCode, Json<serde_json::Value>)> {
    let claims = require_claims(headers)?;
    claims
        .sub
        .parse::<i64>()
        .map_err(|_| (StatusCode::UNAUTHORIZED, Json(json!({ "ok": false, "error": "unauthorized" }))))
}

async fn require_staff(
    state: &AppState,
    headers: &HeaderMap,
) -> Result<Claims, (StatusCode, Json<serde_json::Value>)> {
    let claims = extract_claims_from_header(headers)
        .map_err(|_| (StatusCode::UNAUTHORIZED, Json(serde_json::json!({ "ok": false, "error": "unauthorized" }))))?;
    let user_id = claims.sub.parse::<i64>().ok();
    if let Some(user_id) = user_id {
        let is_staff = sqlx::query_scalar::<_, i64>(
            "SELECT is_staff FROM auth_user WHERE id = ?"
        )
        .bind(user_id)
        .fetch_optional(&state.db)
        .await
        .ok()
        .flatten()
        .unwrap_or(0);
        if is_staff > 0 {
            return Ok(claims);
        }
    }
    Err((StatusCode::FORBIDDEN, Json(serde_json::json!({ "ok": false, "error": "forbidden" }))))
}

fn is_queue_snapshot_stale(generated_at: &str, stale_after_seconds: i64) -> bool {
    if let Ok(parsed) = chrono::NaiveDateTime::parse_from_str(generated_at, "%Y-%m-%d %H:%M:%S") {
        let generated = chrono::Utc.from_utc_datetime(&parsed);
        let age_seconds = (chrono::Utc::now() - generated).num_seconds();
        return age_seconds > stale_after_seconds;
    }
    true
}

async fn fetch_approval_work_item(
    pool: &sqlx::SqlitePool,
    approval_id: i64,
    tenant_id: i64,
) -> Result<Option<(i64, i64)>, sqlx::Error> {
    sqlx::query_as(
        "SELECT tenant_id, work_item_id
         FROM companion_autonomy_approval_requests
         WHERE id = ? AND tenant_id = ?"
    )
    .bind(approval_id)
    .bind(tenant_id)
    .fetch_optional(pool)
    .await
}

pub async fn can_apply_action(
    pool: &sqlx::SqlitePool,
    tenant_id: i64,
    action_id: i64,
) -> Result<bool, sqlx::Error> {
    let action = sqlx::query_as::<_, (i64, bool, String, String)>(
        "SELECT a.work_item_id, a.requires_confirm, a.status, w.status
         FROM companion_autonomy_action_recommendations a
         JOIN companion_autonomy_work_items w ON w.id = a.work_item_id
         WHERE a.tenant_id = ? AND a.id = ? AND w.tenant_id = ?"
    )
    .bind(tenant_id)
    .bind(action_id)
    .bind(tenant_id)
    .fetch_optional(pool)
    .await?;

    let (work_item_id, requires_confirm, action_status, work_item_status) = match action {
        Some(row) => row,
        None => return Ok(false),
    };

    if action_status != "proposed" {
        return Ok(false);
    }

    let allowed_status = matches!(
        work_item_status.as_str(),
        "open" | "ready" | "waiting_approval"
    );
    if !allowed_status {
        return Ok(false);
    }

    if let Ok(Some(settings)) = store::fetch_ai_settings(pool, tenant_id).await {
        if !settings.ai_enabled || settings.kill_switch {
            return Ok(false);
        }
        if settings.ai_mode == "shadow_only" {
            return Ok(false);
        }
    }

    if !requires_confirm {
        return Ok(true);
    }

    let approved: i64 = sqlx::query_scalar(
        "SELECT COUNT(*) FROM companion_autonomy_approval_requests
         WHERE work_item_id = ? AND status = 'approved'"
    )
    .bind(work_item_id)
    .fetch_one(pool)
    .await
    .unwrap_or(0);

    Ok(approved > 0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{routing::get, Router};
    use axum_test::TestServer;
    use chrono::{Duration, Utc};
    use jsonwebtoken::{EncodingKey, Header};
    use sqlx::SqlitePool;

    async fn setup() -> (TestServer, SqlitePool) {
        std::env::set_var("JWT_SECRET", "test-secret");
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        crate::companion_autonomy::schema::run_migrations(&pool).await.unwrap();

        let state = AppState { db: pool.clone() };
        let app = Router::new()
            .route("/api/companion/cockpit/queues", get(cockpit_queues))
            .route("/api/companion/cockpit/status", get(cockpit_status))
            .route("/api/companion/autonomy/status", get(autonomy_status))
            .with_state(state);

        (TestServer::new(app).unwrap(), pool)
    }

    fn make_token(business_id: i64) -> String {
        let exp = (Utc::now() + Duration::hours(1)).timestamp() as usize;
        let claims = Claims {
            sub: "1".to_string(),
            email: "user@example.com".to_string(),
            business_id: Some(business_id),
            exp,
        };
        jsonwebtoken::encode(
            &Header::default(),
            &claims,
            &EncodingKey::from_secret(b"test-secret"),
        )
        .unwrap()
    }

    async fn seed_work_item(pool: &SqlitePool, tenant_id: i64, title: &str) {
        let inputs_json = serde_json::json!({ "transaction_id": tenant_id }).to_string();
        let state_json = serde_json::json!({}).to_string();
        let links_json = serde_json::json!({ "target_url": "/banking" }).to_string();

        let result = sqlx::query(
            "INSERT INTO companion_autonomy_work_items (
                tenant_id, business_id, work_type, surface, status, priority, dedupe_key,
                inputs_json, state_json, due_at, snoozed_until, risk_level, confidence_score,
                requires_approval, customer_title, customer_summary, internal_title, internal_notes,
                links_json, created_at, updated_at
            ) VALUES (?, ?, 'categorize_tx', 'bank', 'open', 50, ?, ?, ?, NULL, NULL,
                      'low', 0.8, 0, ?, 'Summary', 'Internal', 'Notes', ?, datetime('now'), datetime('now'))"
        )
        .bind(tenant_id)
        .bind(tenant_id)
        .bind(format!("dedupe:{}", title))
        .bind(inputs_json)
        .bind(state_json)
        .bind(title)
        .bind(links_json)
        .execute(pool)
        .await
        .unwrap();

        let work_item_id = result.last_insert_rowid();
        sqlx::query(
            "INSERT INTO companion_autonomy_action_recommendations (
                tenant_id, business_id, work_item_id, action_kind, payload_json, preview_effects_json,
                status, requires_confirm, approval_request_id, created_at, updated_at
            ) VALUES (?, ?, ?, 'apply', '{}', '{}', 'proposed', 0, NULL, datetime('now'), datetime('now'))"
        )
        .bind(tenant_id)
        .bind(tenant_id)
        .bind(work_item_id)
        .execute(pool)
        .await
        .unwrap();
    }

    async fn seed_policy(pool: &SqlitePool, tenant_id: i64, mode: &str) {
        sqlx::query(
            "INSERT INTO companion_autonomy_policy (
                tenant_id, mode, breaker_thresholds_json, allowlists_json, budgets_json, updated_at
            ) VALUES (?, ?, '{}', '{}', '{}', datetime('now'))"
        )
        .bind(tenant_id)
        .bind(mode)
        .execute(pool)
        .await
        .unwrap();
    }

    #[tokio::test]
    async fn cockpit_requires_auth() {
        let (server, _pool) = setup().await;
        let response = server.get("/api/companion/cockpit/queues").await;
        response.assert_status(StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn cockpit_status_requires_auth() {
        let (server, _pool) = setup().await;
        let response = server.get("/api/companion/cockpit/status").await;
        response.assert_status(StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn cockpit_tenant_isolation() {
        let (server, pool) = setup().await;
        seed_work_item(&pool, 1, "Tenant A item").await;
        seed_work_item(&pool, 2, "Tenant B item").await;

        let token = make_token(1);
        let response = server
            .get("/api/companion/cockpit/queues")
            .add_header("authorization", format!("Bearer {}", token))
            .await;
        response.assert_status_ok();
        let body: serde_json::Value = response.json();
        let items = body["data"]["ready_queue"].as_array().unwrap();
        let titles: Vec<String> = items
            .iter()
            .filter_map(|item| item.get("title").and_then(|v| v.as_str()).map(|s| s.to_string()))
            .collect();
        assert!(titles.contains(&"Tenant A item".to_string()));
        assert!(!titles.contains(&"Tenant B item".to_string()));
    }

    #[tokio::test]
    async fn cockpit_status_tenant_isolation() {
        let (server, pool) = setup().await;
        seed_policy(&pool, 1, "drafts").await;
        seed_policy(&pool, 2, "autopilot_limited").await;

        let token = make_token(1);
        let response = server
            .get("/api/companion/cockpit/status")
            .add_header("authorization", format!("Bearer {}", token))
            .await;
        response.assert_status_ok();
        let body: serde_json::Value = response.json();
        assert_eq!(body["mode"], "drafts");
    }

    #[tokio::test]
    async fn autonomy_status_requires_auth() {
        let (server, _pool) = setup().await;
        let response = server.get("/api/companion/autonomy/status").await;
        response.assert_status(StatusCode::UNAUTHORIZED);
    }
}
