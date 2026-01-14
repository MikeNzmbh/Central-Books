#![allow(dead_code)]

use sqlx::SqlitePool;

use crate::companion_autonomy::models::AgentOutput;
use crate::companion_autonomy::policy::PolicyConfig;
use crate::companion_autonomy::tool_gateway::ToolGateway;

pub mod categorization;
pub mod narrative;
pub mod orchestrator;
pub mod reconciliation;

pub struct AgentContext {
    pub pool: SqlitePool,
    pub tenant_id: i64,
    pub business_id: i64,
    pub policy: PolicyConfig,
    pub tool_gateway: ToolGateway,
}

#[derive(Debug, Clone, Copy)]
pub enum AgentName {
    Orchestrator,
    Categorization,
    Reconciliation,
}

impl AgentName {
    pub fn as_str(&self) -> &'static str {
        match self {
            AgentName::Orchestrator => "OrchestratorAgent",
            AgentName::Categorization => "CategorizationAgent",
            AgentName::Reconciliation => "ReconciliationAgent",
        }
    }
}

pub async fn run_agent(agent: AgentName, ctx: &AgentContext) -> Result<AgentOutput, String> {
    match agent {
        AgentName::Categorization => categorization::run(ctx).await,
        AgentName::Reconciliation => reconciliation::run(ctx).await,
        AgentName::Orchestrator => orchestrator::run(ctx).await,
    }
}
