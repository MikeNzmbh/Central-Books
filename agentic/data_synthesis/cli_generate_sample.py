"""
CLI - Generate Sample Scenarios

Usage:
    python -m agentic.data_synthesis.cli_generate_sample
"""

import json
import os
from pathlib import Path
from datetime import date

from .generator import generate_scenario_monthly_bookkeeping


def main():
    """Generate sample scenarios and save to submission/sample_scenarios/."""
    print("=" * 60)
    print("Agentic Accounting OS - Synthetic Data Generator")
    print("=" * 60)
    print()
    
    # Output directory
    output_dir = Path(__file__).parent.parent.parent / "submission" / "sample_scenarios"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate scenarios with different seeds
    scenarios = []
    
    for seed in [42, 123, 456]:
        print(f"Generating scenario with seed={seed}...")
        scenario = generate_scenario_monthly_bookkeeping(seed)
        scenarios.append(scenario)
        
        # Save individual scenario
        filename = output_dir / f"scenario_seed_{seed}.json"
        with open(filename, "w") as f:
            json.dump(scenario.model_dump(), f, indent=2, default=str)
        print(f"  Saved: {filename}")
        
        # Print summary
        summary = scenario.summary()
        print(f"  - Documents: {summary['documents']}")
        print(f"  - Transactions: {summary['transactions']}")
        print(f"  - Journal Entries: {summary['journal_entries']}")
        print(f"  - Compliant: {summary['is_compliant']}")
        print(f"  - Audit Risk: {summary['audit_risk']}")
        print()
    
    # Save combined manifest
    manifest = {
        "generated_at": str(date.today()),
        "scenarios": [s.summary() for s in scenarios],
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved manifest: {manifest_file}")
    
    print()
    print("=" * 60)
    print("Generation complete!")
    print(f"Output directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
