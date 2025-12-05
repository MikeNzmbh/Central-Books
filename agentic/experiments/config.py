"""
Experiment Configuration - Define Experiment Modes and Parameters

Modes:
- baseline_heuristic: Rule-based extraction without LLM
- rag_single_agent: Single agent with RAG context
- agentic_full: Full multi-agent system
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ExperimentMode(str, Enum):
    """Experiment mode options."""
    BASELINE_HEURISTIC = "baseline_heuristic"
    RAG_SINGLE_AGENT = "rag_single_agent"
    AGENTIC_FULL = "agentic_full"


class ExperimentConfig(BaseModel):
    """
    Configuration for a single experiment run.
    """
    
    name: str
    mode: ExperimentMode
    description: str = ""
    
    # Input configuration
    scenario_seeds: List[int] = Field(default_factory=lambda: [42, 123, 456])
    document_types: List[str] = Field(
        default_factory=lambda: ["receipt", "invoice", "bank_statement"]
    )
    
    # Processing options
    use_llm: bool = False
    use_memory: bool = False
    use_multi_agent: bool = False
    use_supervisor: bool = False
    
    # Evaluation options
    evaluate_extraction: bool = True
    evaluate_journal: bool = True
    evaluate_compliance: bool = True
    evaluate_audit: bool = True
    
    # Output options
    save_artifacts: bool = True
    verbose: bool = False
    
    @classmethod
    def baseline_heuristic(cls) -> "ExperimentConfig":
        """Create baseline heuristic config."""
        return cls(
            name="baseline_heuristic",
            mode=ExperimentMode.BASELINE_HEURISTIC,
            description="Rule-based extraction without LLM",
            use_llm=False,
            use_memory=False,
            use_multi_agent=False,
            use_supervisor=False,
        )
    
    @classmethod
    def rag_single_agent(cls) -> "ExperimentConfig":
        """Create RAG single agent config."""
        return cls(
            name="rag_single_agent",
            mode=ExperimentMode.RAG_SINGLE_AGENT,
            description="Single agent with RAG context retrieval",
            use_llm=True,
            use_memory=True,
            use_multi_agent=False,
            use_supervisor=False,
        )
    
    @classmethod
    def agentic_full(cls) -> "ExperimentConfig":
        """Create full agentic system config."""
        return cls(
            name="agentic_full",
            mode=ExperimentMode.AGENTIC_FULL,
            description="Full multi-agent system with supervisor",
            use_llm=True,
            use_memory=True,
            use_multi_agent=True,
            use_supervisor=True,
        )


class ScoringWeights(BaseModel):
    """Weights for composite scoring."""
    
    extraction: float = 0.25
    journal: float = 0.30
    compliance: float = 0.25
    audit: float = 0.20
    
    def validate_weights(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = self.extraction + self.journal + self.compliance + self.audit
        return abs(total - 1.0) < 0.01


class ExperimentSuite(BaseModel):
    """Collection of experiments to run."""
    
    name: str = "Full Comparison Suite"
    experiments: List[ExperimentConfig] = Field(default_factory=list)
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    
    @classmethod
    def default_suite(cls) -> "ExperimentSuite":
        """Create default experiment suite with all modes."""
        return cls(
            name="Baseline Comparison Suite",
            experiments=[
                ExperimentConfig.baseline_heuristic(),
                ExperimentConfig.rag_single_agent(),
                ExperimentConfig.agentic_full(),
            ],
        )
