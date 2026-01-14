//! Clover Books - 100% Rust API
//!
//! Native Rust API with no legacy framework dependencies.
//! All endpoints read directly from the SQLite database.

use axum::{
    routing::{get, post},
    Router,
};
use sqlx::SqlitePool;
use std::net::SocketAddr;
use tower_http::cors::{CorsLayer, AllowOrigin};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use axum::http::{HeaderValue, Method, header};

mod db;
mod companion_autonomy;
mod routes;

/// Application state shared across all routes
#[derive(Clone)]
pub struct AppState {
    pub db: SqlitePool,
}

#[tokio::main]
async fn main() {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "clover_api=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load environment variables
    dotenvy::dotenv().ok();

    // Initialize database connection pool
    let db_pool = match db::DbPool::new().await {
        Ok(pool) => {
            tracing::info!("✅ Database connected successfully");
            pool
        }
        Err(e) => {
            tracing::error!("❌ Failed to connect to database: {}", e);
            panic!("Database connection required: {}", e);
        }
    };

    if let Err(e) = companion_autonomy::schema::auto_init(&db_pool.pool).await {
        tracing::error!("❌ Failed to auto-init autonomy schema: {}", e);
        panic!("Autonomy schema auto-init failed: {}", e);
    }

    // Verify onboarding tables exist (fail-fast if migrations not run)
    if let Err(e) = routes::onboarding::verify_schema(&db_pool.pool).await {
        tracing::error!("❌ Onboarding schema verification failed: {}", e);
        tracing::error!("💡 Run: cd rust-api && sqlx migrate run");
        panic!("Onboarding schema missing: {}", e);
    }
    tracing::info!("✅ Onboarding schema verified");


    if let Some(cmd) = std::env::args().nth(1) {
        if run_engine_command(&cmd, &db_pool.pool).await {
            return;
        }
    }

    // Configure CORS - SECURITY: Only allow specific origins
    let allowed_origins: Vec<HeaderValue> = std::env::var("CORS_ALLOWED_ORIGINS")
        .unwrap_or_else(|_| "http://localhost:5173,http://localhost:3000".to_string())
        .split(',')
        .filter_map(|s| s.trim().parse().ok())
        .collect();
    
    let cors = if allowed_origins.is_empty() {
        tracing::warn!("⚠️  No valid CORS origins configured, using localhost defaults");
        CorsLayer::new()
            .allow_origin("http://localhost:5173".parse::<HeaderValue>().unwrap())
            .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE, Method::PATCH])
            .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE, header::ACCEPT])
            .allow_credentials(true)
    } else {
        tracing::info!("✅ CORS configured for {} origin(s)", allowed_origins.len());
        CorsLayer::new()
            .allow_origin(AllowOrigin::list(allowed_origins))
            .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE, Method::PATCH])
            .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE, header::ACCEPT])
            .allow_credentials(true)
    };

    // Shared application state (no more http_client - 100% native)
    let app_state = AppState {
        db: db_pool.pool.clone(),
    };

    // Build router - 100% native Rust
    let app = Router::new()
        // Health check
        .route("/health", get(|| async { "OK" }))
        // Auth routes (native DB)
        .route("/api/auth/login", post(routes::auth::login))
        .route("/api/auth/signup", post(routes::auth::signup))
        .route("/api/auth/me", get(routes::auth::me))
        .route("/api/auth/logout", post(routes::auth::logout))
        .route("/api/auth/config", get(routes::auth::config))
        .route("/api/auth/google/login", get(routes::auth::google_login))
        .route("/api/auth/google/callback", get(routes::auth::google_callback))
        // Banking routes (native matching engine)
        .route("/api/banking/health", get(routes::matching::health))
        .route("/api/banking/find-matches", post(routes::matching::find_matches))
        .route("/api/banking/confirm-match", post(routes::matching::confirm_match))
        .route("/api/banking/allocate", post(routes::matching::allocate))
        .route("/api/banking/progress/:account_id", get(routes::matching::get_progress))
        .route("/api/banking/check-duplicates", post(routes::matching::check_duplicates))
        // Core APIs (native DB)
        .route("/api/dashboard", get(routes::dashboard::dashboard))
        .route("/api/invoices", get(routes::dashboard::list_invoices))
        .route("/api/invoices/list/", get(routes::dashboard::list_invoices)) // Legacy alias
        .route("/api/expenses", get(routes::dashboard::list_expenses))
        .route("/api/expenses/list/", get(routes::dashboard::list_expenses_full)) // Full list for Expenses page
        .route("/api/customers", get(routes::dashboard::list_customers_full))
        .route("/api/customers/list/", get(routes::dashboard::list_customers_full)) // Legacy alias
        .route("/api/products/list/", get(routes::dashboard::list_products)) // Products endpoint
        .route("/api/products/create/", post(routes::dashboard::create_product)) // Create product
        .route("/api/suppliers", get(routes::dashboard::list_suppliers))
        .route("/api/suppliers/list/", get(routes::dashboard::list_suppliers_full)) // Full list for Suppliers page
        .route("/api/categories/list/", get(routes::dashboard::list_categories)) // Categories endpoint
        .route("/api/banking/overview/", get(routes::dashboard::banking_overview)) // Banking overview
        .route("/api/banking/feed/transactions/", get(routes::dashboard::list_feed_transactions)) // Banking feed transactions
        .route("/api/banking/feed/transactions/:id/exclude/", post(routes::dashboard::exclude_feed_transaction))
        .route("/api/banking/feed/transactions/:id/categorize/", post(routes::dashboard::categorize_feed_transaction))
        .route("/api/bank-accounts", get(routes::dashboard::list_bank_accounts))
        .route("/api/bank-accounts/:id/transactions", get(routes::dashboard::list_bank_transactions))
        // AI Companion APIs (native DB)
        .route("/api/companion/issues", get(routes::companion::list_issues))
        .route("/api/companion/issues/:id/dismiss", post(routes::companion::dismiss_issue))
        .route("/api/companion/issues/:id/snooze", post(routes::companion::snooze_issue))
        .route("/api/companion/issues/:id/resolve", post(routes::companion::resolve_issue))
        .route("/api/companion/audits", get(routes::companion::list_audits))
        .route("/api/companion/audits/:id/approve", post(routes::companion::approve_audit))
        .route("/api/companion/audits/:id/reject", post(routes::companion::reject_audit))
        .route("/api/companion/radar", get(routes::companion::radar))
        // Companion v2 API (for Control Tower)
        .route("/api/companion/v2/shadow-events/", get(routes::companion::list_shadow_events))
        .route("/api/companion/v2/shadow-events/:id/apply/", post(routes::companion::apply_shadow_event))
        .route("/api/companion/v2/shadow-events/:id/reject/", post(routes::companion::reject_shadow_event))
        .route("/api/companion/v2/settings/", get(routes::companion::get_ai_settings_v2))
        .route("/api/companion/v2/settings/", axum::routing::patch(routes::companion::patch_ai_settings_v2))
        .route("/api/companion/v2/policy/", get(routes::companion::get_business_policy_v2))
        .route("/api/companion/v2/policy/", axum::routing::patch(routes::companion::patch_business_policy_v2))
        .route("/api/companion/v2/proposals/", get(routes::companion::list_proposals))
        .route("/api/companion/v2/proposals/:id/apply/", post(routes::companion::apply_proposal))
        .route("/api/companion/v2/proposals/:id/reject/", post(routes::companion::reject_proposal))
        // Companion autonomy engine APIs
        .route("/api/companion/autonomy/status", get(routes::companion_autonomy::autonomy_status))
        .route("/api/companion/autonomy/runs", get(routes::companion_autonomy::list_runs))
        .route("/api/companion/autonomy/work/:id", get(routes::companion_autonomy::work_detail))
        .route("/api/companion/autonomy/work/:id/dismiss", post(routes::companion_autonomy::dismiss_work_item))
        .route("/api/companion/autonomy/work/:id/snooze", post(routes::companion_autonomy::snooze_work_item))
        .route(
            "/api/companion/autonomy/work/:id/request-approval",
            post(routes::companion_autonomy::request_approval),
        )
        .route(
            "/api/companion/autonomy/approval/:id/approve",
            post(routes::companion_autonomy::approve_request),
        )
        .route(
            "/api/companion/autonomy/approval/:id/reject",
            post(routes::companion_autonomy::reject_request),
        )
        .route("/api/companion/autonomy/actions/:id/apply", post(routes::companion_autonomy::apply_action))
        .route(
            "/api/companion/autonomy/actions/batch-apply",
            post(routes::companion_autonomy::batch_apply_actions),
        )
        .route("/api/companion/autonomy/tick", post(routes::companion_autonomy::engine_tick))
        .route(
            "/api/companion/autonomy/materialize",
            post(routes::companion_autonomy::engine_materialize),
        )
        .route("/api/companion/autonomy/policy", post(routes::companion_autonomy::update_policy))
        .route("/api/companion/cockpit/status", get(routes::companion_autonomy::cockpit_status))
        .route("/api/companion/cockpit/queues", get(routes::companion_autonomy::cockpit_queues))
        // Agentic Invoice AI APIs
        .route("/api/agentic/invoices/runs", get(routes::agentic::list_runs))
        .route("/api/agentic/invoices/run/:id", get(routes::agentic::get_run))
        .route("/api/agentic/invoices/run", post(routes::agentic::create_run))
        .route("/api/agentic/invoices/:id/approve", post(routes::agentic::approve_invoice))
        .route("/api/agentic/invoices/:id/discard", post(routes::agentic::discard_invoice))
        // Agentic Receipts AI APIs
        .route("/api/agentic/receipts/runs", get(routes::agentic::list_receipt_runs))
        .route("/api/agentic/receipts/run/:id", get(routes::agentic::get_receipt_run))
        .route("/api/agentic/receipts/run", post(routes::agentic::create_receipt_run))
        .route("/api/agentic/receipts/:id/approve", post(routes::agentic::approve_receipt))
        .route("/api/agentic/receipts/:id/discard", post(routes::agentic::discard_receipt))
        // Agentic Companion APIs (for Control Tower)
        .route("/api/agentic/companion/summary", get(routes::agentic::companion_summary))
        .route("/api/agentic/companion/issues", get(routes::agentic::companion_issues))
        .route("/api/agentic/companion/issues/:id", axum::routing::patch(routes::agentic::update_companion_issue))
        .route("/api/agentic/companion/context-summary/", get(routes::agentic::companion_context_summary))
        // Reconciliation APIs
        .route("/api/reconciliation/accounts/", get(routes::reconciliation::list_accounts))
        .route("/api/reconciliation/accounts/:id/periods/", get(routes::reconciliation::list_periods))
        .route("/api/reconciliation/session/", get(routes::reconciliation::get_session))
        .route("/api/reconciliation/matches/", get(routes::reconciliation::get_matches))
        .route("/api/reconciliation/confirm-match/", post(routes::reconciliation::confirm_match))
        .route("/api/reconciliation/add-as-new/", post(routes::reconciliation::add_as_new))
        .route("/api/reconciliation/session/:id/exclude/", post(routes::reconciliation::exclude_transaction))
        .route("/api/reconciliation/session/:id/unmatch/", post(routes::reconciliation::unmatch_transaction))
        .route("/api/reconciliation/session/:id/set_statement_balance/", post(routes::reconciliation::set_statement_balance))
        .route("/api/reconciliation/sessions/:id/complete/", post(routes::reconciliation::complete_session))
        .route("/api/reconciliation/sessions/:id/reopen/", post(routes::reconciliation::reopen_session))
        .route("/api/reconciliation/sessions/:id/delete/", post(routes::reconciliation::delete_session))
        .route("/api/reconciliation/create-adjustment/", post(routes::reconciliation::create_adjustment))
        // Onboarding APIs
        .route("/api/onboarding/profile", get(routes::onboarding::get_profile))
        .route("/api/onboarding/profile", axum::routing::put(routes::onboarding::update_profile))
        .route("/api/onboarding/event", post(routes::onboarding::log_event))
        .route("/api/consents/grant", post(routes::onboarding::grant_consent))
        .route("/api/consents/revoke", post(routes::onboarding::revoke_consent))
        .route("/api/ai/handshake/confirm", post(routes::onboarding::confirm_ai_handshake))
        // Tax Guardian APIs
        .route("/api/tax/periods/", get(routes::tax::list_periods))
        .route("/api/tax/periods/:period_key/", get(routes::tax::get_snapshot))
        .route("/api/tax/periods/:period_key/anomalies/", get(routes::tax::list_anomalies))
        .route("/api/tax/periods/:period_key/refresh/", post(routes::tax::refresh_period))
        .route("/api/tax/periods/:period_key/status/", post(routes::tax::update_status))
        .route("/api/tax/periods/:period_key/anomalies/:anomaly_id/", axum::routing::patch(routes::tax::update_anomaly))
        .route("/api/tax/periods/:period_key/llm-enrich/", post(routes::tax::llm_enrich))
        .route("/api/tax/periods/:period_key/reset/", post(routes::tax::reset_period))
        .route("/api/tax/periods/:period_key/payments/", post(routes::tax::create_payment))
        .route("/api/tax/periods/:period_key/payments/:payment_id/", axum::routing::patch(routes::tax::update_payment))
        .route("/api/tax/periods/:period_key/payments/:payment_id/delete/", post(routes::tax::delete_payment))
        // Add shared state for all routes
        .with_state(app_state)

        // Add middleware
        .layer(cors)
        .layer(TraceLayer::new_for_http());

    // Start server
    let addr = SocketAddr::from(([0, 0, 0, 0], 3001));
    tracing::info!("🚀 Clover API starting on http://{}", addr);
    tracing::info!("🦀 100% Native Rust - No legacy framework dependencies");
    tracing::info!("🔐 Auth: /api/auth/*");
    tracing::info!("💰 Banking: /api/banking/* (native matching engine)");
    tracing::info!("📋 Core: /api/dashboard, invoices, expenses, customers, suppliers");
    tracing::info!("🤖 Companion: /api/companion/*");
    tracing::info!("🗄️ Database: SQLite");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn run_engine_command(cmd: &str, pool: &SqlitePool) -> bool {
    let args: Vec<String> = std::env::args().collect();
    match cmd {
        "companion-engine-tick" => {
            let tenants = resolve_tenants(&args, pool).await;
            if let Err(err) = companion_autonomy::scheduler::tick(pool, tenants, None).await {
                tracing::error!("Engine tick failed: {}", err);
            } else {
                tracing::info!("Engine tick completed");
            }
            true
        }
        "companion-engine-materialize" => {
            let tenants = resolve_tenants(&args, pool).await;
            let stale = parse_arg(&args, "--max-age-minutes")
                .and_then(|v| v.parse::<i64>().ok())
                .unwrap_or_else(|| companion_autonomy::policy::PolicyConfig::from_env().snapshot_stale_minutes);
            if let Err(err) = companion_autonomy::scheduler::materialize(pool, tenants, stale, None).await {
                tracing::error!("Engine materialize failed: {}", err);
            } else {
                tracing::info!("Engine materialize completed");
            }
            true
        }
        "companion-engine-run-agent" => {
            let tenants = resolve_tenants(&args, pool).await;
            let agent_name = parse_arg(&args, "--agent");
            let work_item_id = parse_arg(&args, "--work-item")
                .and_then(|v| v.parse::<i64>().ok());
            if let Some(agent_name) = agent_name {
                if let Some(agent) = map_agent_name(&agent_name) {
                    for tenant_id in tenants {
                        let result = if let Some(work_item_id) = work_item_id {
                            companion_autonomy::scheduler::run_agent_for_work_item(pool, tenant_id, agent, work_item_id)
                                .await
                        } else {
                            companion_autonomy::scheduler::run_agent_for_tenant(pool, tenant_id, agent).await
                        };
                        if let Err(err) = result {
                            tracing::error!("Engine run-agent failed: {}", err);
                        }
                    }
                } else {
                    tracing::error!("Unknown agent: {}", agent_name);
                }
            } else {
                tracing::error!("Missing --agent for companion-engine-run-agent");
            }
            true
        }
        "companion-engine-worker" => {
            let once = args.iter().any(|a| a == "--once");
            let limit = parse_arg(&args, "--limit")
                .and_then(|v| v.parse::<i64>().ok())
                .unwrap_or(10);
            if let Err(err) = companion_autonomy::scheduler::run_worker(pool, once, limit).await {
                tracing::error!("Engine worker failed: {}", err);
            }
            true
        }
        _ => false,
    }
}

async fn resolve_tenants(args: &[String], pool: &SqlitePool) -> Vec<i64> {
    if let Some(value) = parse_arg(args, "--tenant") {
        if value == "all" {
            return companion_autonomy::store::list_business_ids(pool).await.unwrap_or_else(|_| vec![1]);
        }
        if let Ok(id) = value.parse::<i64>() {
            return vec![id];
        }
    }
    companion_autonomy::store::list_business_ids(pool).await.unwrap_or_else(|_| vec![1])
}

fn parse_arg(args: &[String], key: &str) -> Option<String> {
    let mut iter = args.iter();
    while let Some(arg) = iter.next() {
        if arg == key {
            return iter.next().cloned();
        }
    }
    None
}

fn map_agent_name(name: &str) -> Option<companion_autonomy::agents::AgentName> {
    match name {
        "OrchestratorAgent" | "orchestrator" | "orchestrator-agent" => {
            Some(companion_autonomy::agents::AgentName::Orchestrator)
        }
        "CategorizationAgent" | "categorization" | "categorization-agent" => {
            Some(companion_autonomy::agents::AgentName::Categorization)
        }
        "ReconciliationAgent" | "reconciliation" | "reconciliation-agent" => {
            Some(companion_autonomy::agents::AgentName::Reconciliation)
        }
        _ => None,
    }
}
