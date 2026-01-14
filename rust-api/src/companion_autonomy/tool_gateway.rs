#![allow(dead_code)]

use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use reqwest::Url;

use crate::companion_autonomy::policy::BudgetConfig;
use crate::companion_autonomy::store;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResponse {
    pub text: String,
    pub json: serde_json::Value,
    pub meta: serde_json::Value,
    pub tokens_used: i64,
    pub cost_estimate: f64,
}

pub struct ToolGateway {
    pub pool: SqlitePool,
    pub budget: BudgetConfig,
    pub allowed_domains: Vec<String>,
    pub allowed_models: Vec<String>,
    pub llm_mode: ToolMode,
    pub tool_mode: ToolMode,
    pub provider: Box<dyn ToolProvider + Send + Sync>,
}

#[derive(Debug)]
pub enum ToolGatewayError {
    BudgetExceeded(String),
    Blocked(String),
    Provider(String),
    Storage(String),
}

pub trait ToolProvider {
    fn name(&self) -> &'static str;
    fn run_llm(&self, model_hint: &str, messages: &[serde_json::Value]) -> Result<ToolResponse, String>;
}

pub struct StubProvider;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ToolMode {
    Live,
    Mock,
}

impl ToolMode {
    fn from_env(key: &str) -> Self {
        match std::env::var(key).unwrap_or_default().to_lowercase().as_str() {
            "mock" => ToolMode::Mock,
            _ => ToolMode::Live,
        }
    }
}

impl ToolProvider for StubProvider {
    fn name(&self) -> &'static str {
        "stub"
    }

    fn run_llm(&self, model_hint: &str, messages: &[serde_json::Value]) -> Result<ToolResponse, String> {
        let summary = format!("Stub response for {} ({} messages)", model_hint, messages.len());
        Ok(ToolResponse {
            text: summary.clone(),
            json: serde_json::json!({ "summary": summary }),
            meta: serde_json::json!({ "provider": "stub" }),
            tokens_used: 42,
            cost_estimate: 0.0,
        })
    }
}

impl ToolGateway {
    pub fn new(pool: SqlitePool) -> Self {
        Self {
            pool,
            budget: BudgetConfig::from_env(),
            allowed_domains: env_list("ENGINE_ALLOWLIST_DOMAINS"),
            allowed_models: env_list("ENGINE_LLM_ALLOWED_MODELS"),
            llm_mode: ToolMode::from_env("LLM_MODE"),
            tool_mode: ToolMode::from_env("TOOL_MODE"),
            provider: Box::new(StubProvider),
        }
    }

    pub fn with_provider(mut self, provider: Box<dyn ToolProvider + Send + Sync>) -> Self {
        self.provider = provider;
        self
    }

    pub async fn run_llm(
        &self,
        tenant_id: i64,
        business_id: i64,
        agent_run_id: Option<i64>,
        purpose: &str,
        messages: Vec<serde_json::Value>,
        model_hint: &str,
    ) -> Result<ToolResponse, ToolGatewayError> {
        if self.allowed_models.is_empty() {
            let reason = "model allowlist is empty".to_string();
            self.log_tool_call(
                tenant_id,
                business_id,
                agent_run_id,
                "llm",
                "blocked",
                serde_json::json!({"purpose": purpose, "model": model_hint, "messages": messages.len()}),
                serde_json::json!({"blocked": true, "reason": reason}),
                0,
                0.0,
                0,
                false,
                Some(reason.clone()),
            )
            .await;
            return Err(ToolGatewayError::Blocked(reason));
        }

        let allowlisted = self
            .allowed_models
            .iter()
            .any(|m| m.eq_ignore_ascii_case(model_hint));
        if !self.allowed_models.is_empty() && !allowlisted {
            let reason = format!("model not allowlisted: {}", model_hint);
            self.log_tool_call(
                tenant_id,
                business_id,
                agent_run_id,
                "llm",
                "blocked",
                serde_json::json!({"purpose": purpose, "model": model_hint, "messages": messages.len()}),
                serde_json::json!({"blocked": true, "reason": reason}),
                0,
                0.0,
                0,
                false,
                Some(reason.clone()),
            )
            .await;
            return Err(ToolGatewayError::Blocked(reason));
        }

        if let Err(err) = self.enforce_budget(tenant_id).await {
            self.emit_breaker(
                tenant_id,
                business_id,
                "budget",
                self.budget.tool_calls_per_day as f64,
                self.budget.tool_calls_per_day as f64 + 1.0,
                "pause",
                None,
            )
            .await;
            return Err(err);
        }

        let (response, provider_name) = if self.llm_mode == ToolMode::Mock {
            let summary = format!("Mock LLM response for {} ({} messages)", model_hint, messages.len());
            (
                ToolResponse {
                    text: summary.clone(),
                    json: serde_json::json!({ "summary": summary, "mode": "mock" }),
                    meta: serde_json::json!({ "provider": "mock" }),
                    tokens_used: 0,
                    cost_estimate: 0.0,
                },
                "mock",
            )
        } else {
            (
                self.provider
                    .run_llm(model_hint, &messages)
                    .map_err(ToolGatewayError::Provider)?,
                self.provider.name(),
            )
        };

        self.log_tool_call(
            tenant_id,
            business_id,
            agent_run_id,
            "llm",
            provider_name,
            serde_json::json!({"purpose": purpose, "model": model_hint, "messages": messages.len()}),
            response.meta.clone(),
            response.tokens_used,
            response.cost_estimate,
            0,
            allowlisted,
            None,
        )
        .await;

        Ok(response)
    }

    pub async fn fetch_url(
        &self,
        tenant_id: i64,
        business_id: i64,
        agent_run_id: Option<i64>,
        url: &str,
    ) -> Result<serde_json::Value, ToolGatewayError> {
        if self.allowed_domains.is_empty() {
            let reason = "domain allowlist is empty".to_string();
            self.log_tool_call(
                tenant_id,
                business_id,
                agent_run_id,
                "fetch_url",
                "blocked",
                serde_json::json!({"url": url}),
                serde_json::json!({"blocked": true, "reason": reason}),
                0,
                0.0,
                0,
                false,
                Some(reason.clone()),
            )
            .await;
            return Err(ToolGatewayError::Blocked(reason));
        }

        let allowlisted = is_allowlisted_url(url, &self.allowed_domains);

        if !allowlisted {
            let reason = "domain not allowlisted".to_string();
            self.log_tool_call(
                tenant_id,
                business_id,
                agent_run_id,
                "fetch_url",
                "stub",
                serde_json::json!({"url": url}),
                serde_json::json!({"blocked": true, "reason": reason}),
                0,
                0.0,
                0,
                false,
                Some("domain not allowlisted".to_string()),
            )
            .await;
            return Err(ToolGatewayError::Blocked(reason));
        }

        self.enforce_budget(tenant_id).await?;

        let response = if self.tool_mode == ToolMode::Mock {
            serde_json::json!({ "clean_text": "", "meta": {"url": url, "mode": "mock"} })
        } else {
            serde_json::json!({ "clean_text": "", "meta": {"url": url, "mode": "live"} })
        };

        self.log_tool_call(
            tenant_id,
            business_id,
            agent_run_id,
            "fetch_url",
            if self.tool_mode == ToolMode::Mock { "mock" } else { "stub" },
            serde_json::json!({"url": url}),
            serde_json::json!({"ok": true}),
            0,
            0.0,
            0,
            true,
            None,
        )
        .await;

        Ok(response)
    }

    async fn enforce_budget(&self, tenant_id: i64) -> Result<(), ToolGatewayError> {
        let (tool_calls, tokens) = store::tool_usage_last_day(&self.pool, tenant_id)
            .await
            .map_err(|e| ToolGatewayError::Storage(e.to_string()))?;
        if tool_calls >= self.budget.tool_calls_per_day {
            return Err(ToolGatewayError::BudgetExceeded(
                "tool call budget exceeded".to_string(),
            ));
        }
        if tokens >= self.budget.tokens_per_day {
            return Err(ToolGatewayError::BudgetExceeded(
                "token budget exceeded".to_string(),
            ));
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    async fn log_tool_call(
        &self,
        tenant_id: i64,
        business_id: i64,
        agent_run_id: Option<i64>,
        tool_name: &str,
        provider: &str,
        request_meta: serde_json::Value,
        response_meta: serde_json::Value,
        tokens_used: i64,
        cost_estimate: f64,
        duration_ms: i64,
        allowlisted: bool,
        blocked_reason: Option<String>,
    ) {
        let _ = store::insert_tool_call(
            &self.pool,
            tenant_id,
            business_id,
            agent_run_id,
            tool_name,
            provider,
            &request_meta,
            &response_meta,
            tokens_used,
            cost_estimate,
            duration_ms,
            allowlisted,
            blocked_reason.as_deref(),
        )
        .await;
    }

    #[allow(clippy::too_many_arguments)]
    async fn emit_breaker(
        &self,
        tenant_id: i64,
        business_id: i64,
        breaker_type: &str,
        threshold: f64,
        observed_value: f64,
        action_taken: &str,
        related_work_item_id: Option<i64>,
    ) {
        let _ = store::insert_breaker_event(
            &self.pool,
            tenant_id,
            business_id,
            breaker_type,
            threshold,
            observed_value,
            action_taken,
            related_work_item_id,
        )
        .await;
    }
}

fn is_allowlisted_url(url: &str, allowed_domains: &[String]) -> bool {
    let host = match Url::parse(url).ok().and_then(|parsed| parsed.host_str().map(|h| h.to_lowercase())) {
        Some(host) => host,
        None => return false,
    };
    allowed_domains.iter().any(|domain| {
        let Some(normalized) = normalize_allowlist_domain(domain) else {
            return false;
        };
        host == normalized || host.ends_with(&format!(".{}", normalized))
    })
}

fn normalize_allowlist_domain(entry: &str) -> Option<String> {
    let trimmed = entry.trim().trim_end_matches('/');
    if trimmed.is_empty() {
        return None;
    }
    if let Ok(url) = Url::parse(trimmed) {
        return url.host_str().map(|host| host.to_lowercase());
    }
    Some(trimmed.to_lowercase())
}

fn env_list(key: &str) -> Vec<String> {
    std::env::var(key)
        .unwrap_or_default()
        .split(',')
        .filter_map(|value| {
            let trimmed = value.trim();
            if trimmed.is_empty() {
                None
            } else {
                Some(trimmed.to_string())
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_autonomy::schema;

    struct PanicProvider;

    impl ToolProvider for PanicProvider {
        fn name(&self) -> &'static str {
            "panic"
        }

        fn run_llm(&self, _model_hint: &str, _messages: &[serde_json::Value]) -> Result<ToolResponse, String> {
            panic!("provider should not be called in mock mode");
        }
    }

    #[tokio::test]
    async fn tool_gateway_default_deny() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();

        let mut gateway = ToolGateway::new(pool.clone());
        gateway.allowed_models = vec![];
        gateway.llm_mode = ToolMode::Mock;

        let response = gateway
            .run_llm(1, 1, None, "test", vec![], "stub")
            .await;
        assert!(matches!(response, Err(ToolGatewayError::Blocked(_))));
    }

    #[tokio::test]
    async fn tool_gateway_mock_mode_skips_provider() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();

        let mut gateway = ToolGateway::new(pool.clone()).with_provider(Box::new(PanicProvider));
        gateway.allowed_models = vec!["stub".to_string()];
        gateway.llm_mode = ToolMode::Mock;

        let response = gateway
            .run_llm(1, 1, None, "test", vec![], "stub")
            .await;
        assert!(response.is_ok());
    }

    #[tokio::test]
    async fn tool_gateway_default_deny_domains() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();

        let mut gateway = ToolGateway::new(pool.clone());
        gateway.allowed_domains = vec![];
        gateway.tool_mode = ToolMode::Mock;

        let response = gateway.fetch_url(1, 1, None, "https://example.com").await;
        assert!(matches!(response, Err(ToolGatewayError::Blocked(_))));
    }

    #[tokio::test]
    async fn tool_gateway_enforces_budget() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();

        let mut gateway = ToolGateway::new(pool.clone());
        gateway.allowed_models = vec!["stub".to_string()];
        gateway.llm_mode = ToolMode::Mock;
        gateway.budget.tool_calls_per_day = 1;
        let response = gateway
            .run_llm(1, 1, None, "test", vec![], "stub")
            .await;
        assert!(response.is_ok());
        let second = gateway
            .run_llm(1, 1, None, "test", vec![], "stub")
            .await;
        assert!(second.is_err());
    }

    #[tokio::test]
    async fn tool_gateway_blocks_non_allowlisted_model() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();

        let mut gateway = ToolGateway::new(pool.clone());
        gateway.allowed_models = vec!["deepseek-chat".to_string()];
        gateway.llm_mode = ToolMode::Mock;

        let response = gateway
            .run_llm(1, 1, None, "test", vec![], "gpt-4o-mini")
            .await;
        assert!(response.is_err());
    }

    #[tokio::test]
    async fn tool_gateway_mock_mode_is_deterministic() {
        let pool = SqlitePool::connect("sqlite::memory:").await.unwrap();
        schema::run_migrations(&pool).await.unwrap();

        let mut gateway = ToolGateway::new(pool.clone());
        gateway.allowed_models = vec!["stub".to_string()];
        gateway.llm_mode = ToolMode::Mock;

        let response = gateway
            .run_llm(1, 1, None, "test", vec![serde_json::json!({"role": "user", "content": "Hi"})], "stub")
            .await
            .unwrap();
        assert!(response.text.contains("Mock LLM response"));
    }
}
