"""
CLI - Run All Experiments

Usage:
    python -m agentic.experiments.cli_run_all
"""

import json
from pathlib import Path
from datetime import datetime

from .config import ExperimentConfig
from .runner import run_experiment, run_all_baselines


def main():
    """Run all baseline experiments and save results."""
    print("=" * 60)
    print("Agentic Accounting OS - Experiment Runner")
    print("=" * 60)
    print()
    
    # Output directory
    output_dir = Path(__file__).parent.parent.parent / "submission" / "experiments"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run all experiments
    print("Running experiments...")
    print()
    
    all_results = {}
    
    configs = [
        ExperimentConfig.baseline_heuristic(),
        ExperimentConfig.rag_single_agent(),
        ExperimentConfig.agentic_full(),
    ]
    
    for config in configs:
        print(f"Running: {config.name}")
        print(f"  Mode: {config.mode.value}")
        print(f"  Description: {config.description}")
        
        result = run_experiment(config)
        all_results[config.name] = result
        
        print(f"  Composite Score: {result.aggregate_scores.composite_score:.4f}")
        print(f"  - Extraction: {result.aggregate_scores.extraction_accuracy:.4f}")
        print(f"  - Journal: {result.aggregate_scores.journal_correctness:.4f}")
        print(f"  - Compliance: {result.aggregate_scores.compliance_correctness:.4f}")
        print(f"  - Audit: {result.aggregate_scores.audit_correctness:.4f}")
        print()
    
    # Save results
    results_file = output_dir / "results_baselines.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "generated_at": datetime.utcnow().isoformat(),
                "experiments": {k: v.to_dict() for k, v in all_results.items()},
            },
            f,
            indent=2,
        )
    print(f"Saved results: {results_file}")
    
    # Generate comparison table
    print()
    print("=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print()
    print(f"{'Mode':<25} {'Extract':<10} {'Journal':<10} {'Compl.':<10} {'Audit':<10} {'Composite':<10}")
    print("-" * 75)
    
    for name, result in all_results.items():
        s = result.aggregate_scores
        print(f"{name:<25} {s.extraction_accuracy:.4f}    {s.journal_correctness:.4f}    {s.compliance_correctness:.4f}   {s.audit_correctness:.4f}   {s.composite_score:.4f}")
    
    print()
    print("=" * 60)
    print("Experiments complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
