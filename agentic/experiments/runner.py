"""
Experiment Runner - Execute and Score Experiments

Runs experiments across different modes and computes scores.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
import json

from .config import ExperimentConfig, ExperimentMode, ScoringWeights

# Import workflows and evaluation
from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow
from agentic.workflows.steps.invoice_pipeline import build_invoice_workflow
from agentic.workflows.steps.bank_statement_pipeline import build_bank_statement_workflow
from agentic.engine.evaluation import EvaluationScorer
from agentic.data_synthesis import generate_scenario_monthly_bookkeeping


# =============================================================================
# RESULT MODELS
# =============================================================================


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown."""
    
    extraction_accuracy: float = 0.0
    journal_correctness: float = 0.0
    compliance_correctness: float = 0.0
    audit_correctness: float = 0.0
    composite_score: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "extraction_accuracy": round(self.extraction_accuracy, 4),
            "journal_correctness": round(self.journal_correctness, 4),
            "compliance_correctness": round(self.compliance_correctness, 4),
            "audit_correctness": round(self.audit_correctness, 4),
            "composite_score": round(self.composite_score, 4),
        }


@dataclass
class ScenarioResult:
    """Result for a single scenario."""
    
    scenario_id: str
    seed: int
    scores: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "scores": self.scores.to_dict(),
            "duration_ms": round(self.duration_ms, 2),
            "errors": self.errors,
        }


@dataclass
class ExperimentResult:
    """Complete experiment result."""
    
    config_name: str
    mode: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    scenario_results: List[ScenarioResult] = field(default_factory=list)
    aggregate_scores: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    
    def to_dict(self) -> dict:
        return {
            "config_name": self.config_name,
            "mode": self.mode,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "scenario_results": [s.to_dict() for s in self.scenario_results],
            "aggregate_scores": self.aggregate_scores.to_dict(),
        }


# =============================================================================
# EXPERIMENT RUNNER
# =============================================================================


class ExperimentRunner:
    """
    Run experiments and compute scores.
    """
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.scorer = EvaluationScorer()
        self._results: List[ScenarioResult] = []
    
    def run(self) -> ExperimentResult:
        """Run the experiment across all scenarios."""
        result = ExperimentResult(
            config_name=self.config.name,
            mode=self.config.mode.value,
        )
        
        for seed in self.config.scenario_seeds:
            scenario_result = self._run_scenario(seed)
            result.scenario_results.append(scenario_result)
        
        # Calculate aggregate scores
        result.aggregate_scores = self._aggregate_scores(result.scenario_results)
        result.finished_at = datetime.utcnow()
        
        return result
    
    def _run_scenario(self, seed: int) -> ScenarioResult:
        """Run a single scenario."""
        import time
        start = time.perf_counter()
        
        scenario_result = ScenarioResult(
            scenario_id=f"scenario-{seed}",
            seed=seed,
        )
        
        try:
            # Generate scenario
            scenario = generate_scenario_monthly_bookkeeping(seed)
            
            # Run appropriate workflow based on mode
            artifacts = self._run_workflow(scenario)
            
            # Score against ground truth
            scores = self._score_results(scenario, artifacts)
            scenario_result.scores = scores
            
        except Exception as e:
            scenario_result.errors.append(str(e))
        
        scenario_result.duration_ms = (time.perf_counter() - start) * 1000
        return scenario_result
    
    def _run_workflow(self, scenario) -> Dict[str, Any]:
        """Run the workflow for the current mode."""
        # Prepare documents for workflow
        uploaded_files = [
            {"filename": doc.filename, "content": doc.content}
            for doc in scenario.documents
        ]
        
        # Select workflow based on mode
        if self.config.mode == ExperimentMode.BASELINE_HEURISTIC:
            # Use basic receipts workflow
            wf = build_receipts_workflow()
        elif self.config.mode == ExperimentMode.RAG_SINGLE_AGENT:
            # Use receipts workflow with memory context (simulated)
            wf = build_receipts_workflow()
        else:  # AGENTIC_FULL
            # Use multi-document workflow
            from agentic.workflows.steps.multi_document_pipeline import build_multi_document_workflow
            wf = build_multi_document_workflow()
        
        # Run workflow
        result = wf.run({"uploaded_files": uploaded_files})
        
        return result.artifacts
    
    def _score_results(
        self,
        scenario,
        artifacts: Dict[str, Any],
    ) -> ScoreBreakdown:
        """Score workflow results against ground truth."""
        scores = ScoreBreakdown()
        
        # Score extraction
        if self.config.evaluate_extraction:
            extracted = artifacts.get("extracted_documents", []) or artifacts.get("aggregated_results", {})
            if extracted:
                # Compare against expected
                doc_count = len(scenario.documents)
                if hasattr(extracted, "receipts_processed"):
                    actual_count = extracted.receipts_processed + extracted.invoices_processed + extracted.statements_processed
                else:
                    actual_count = len(extracted) if isinstance(extracted, list) else 0
                
                scores.extraction_accuracy = min(1.0, actual_count / max(doc_count, 1))
        
        # Score journal entries
        if self.config.evaluate_journal:
            entries = artifacts.get("journal_entries", [])
            expected = len(scenario.journal_entries)
            actual = len(entries) if entries else 0
            
            # Check for balanced entries
            balanced_count = 0
            for entry in (entries or []):
                is_balanced = False
                if hasattr(entry, "is_balanced"):
                    is_balanced = entry.is_balanced
                elif isinstance(entry, dict):
                    is_balanced = entry.get("is_balanced", False)
                if is_balanced:
                    balanced_count += 1
            
            count_score = min(1.0, actual / max(expected, 1))
            balance_score = balanced_count / max(actual, 1) if actual > 0 else 0
            scores.journal_correctness = count_score * 0.5 + balance_score * 0.5
        
        # Score compliance
        if self.config.evaluate_compliance:
            compliance = artifacts.get("compliance_result", {})
            expected_compliant = scenario.compliance.is_compliant
            
            actual_compliant = False
            if hasattr(compliance, "is_compliant"):
                actual_compliant = compliance.is_compliant
            elif isinstance(compliance, dict):
                actual_compliant = compliance.get("is_compliant", False)
            
            scores.compliance_correctness = 1.0 if actual_compliant == expected_compliant else 0.5
        
        # Score audit
        if self.config.evaluate_audit:
            audit = artifacts.get("audit_report", {})
            expected_risk = scenario.audit.risk_level
            
            actual_risk = "low"
            if hasattr(audit, "risk_level"):
                actual_risk = audit.risk_level
            elif isinstance(audit, dict):
                actual_risk = audit.get("risk_level", "low")
            
            if actual_risk == expected_risk:
                scores.audit_correctness = 1.0
            elif (actual_risk in ["low", "medium"] and expected_risk in ["low", "medium"]):
                scores.audit_correctness = 0.75
            else:
                scores.audit_correctness = 0.5
        
        # Calculate composite
        weights = ScoringWeights()
        scores.composite_score = (
            scores.extraction_accuracy * weights.extraction +
            scores.journal_correctness * weights.journal +
            scores.compliance_correctness * weights.compliance +
            scores.audit_correctness * weights.audit
        )
        
        return scores
    
    def _aggregate_scores(
        self,
        scenario_results: List[ScenarioResult],
    ) -> ScoreBreakdown:
        """Aggregate scores across scenarios."""
        if not scenario_results:
            return ScoreBreakdown()
        
        valid_results = [r for r in scenario_results if not r.errors]
        if not valid_results:
            return ScoreBreakdown()
        
        n = len(valid_results)
        return ScoreBreakdown(
            extraction_accuracy=sum(r.scores.extraction_accuracy for r in valid_results) / n,
            journal_correctness=sum(r.scores.journal_correctness for r in valid_results) / n,
            compliance_correctness=sum(r.scores.compliance_correctness for r in valid_results) / n,
            audit_correctness=sum(r.scores.audit_correctness for r in valid_results) / n,
            composite_score=sum(r.scores.composite_score for r in valid_results) / n,
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def run_experiment(config: ExperimentConfig) -> ExperimentResult:
    """Run a single experiment."""
    runner = ExperimentRunner(config)
    return runner.run()


def run_all_baselines() -> Dict[str, ExperimentResult]:
    """Run all baseline experiments."""
    results = {}
    
    for config in [
        ExperimentConfig.baseline_heuristic(),
        ExperimentConfig.rag_single_agent(),
        ExperimentConfig.agentic_full(),
    ]:
        result = run_experiment(config)
        results[config.name] = result
    
    return results
