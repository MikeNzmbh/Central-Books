use serde_json::json;

use crate::companion_autonomy::agents::{categorization, reconciliation, AgentContext};
use crate::companion_autonomy::models::AgentOutput;

pub async fn run(ctx: &AgentContext) -> Result<AgentOutput, String> {
    let mut output = AgentOutput::empty();

    let reconciliation_output = reconciliation::run(ctx).await?;
    merge_output(&mut output, reconciliation_output);

    let categorization_output = categorization::run(ctx).await?;
    merge_output(&mut output, categorization_output);

    output.signals.push(json!({
        "type": "orchestrator_summary",
        "work_items": output.work_items.len()
    }));

    Ok(output)
}

fn merge_output(target: &mut AgentOutput, other: AgentOutput) {
    target.signals.extend(other.signals);
    target.recommendations.extend(other.recommendations);
    target.evidence_refs.extend(other.evidence_refs);
    target.work_items.extend(other.work_items);
}
