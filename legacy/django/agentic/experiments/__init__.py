"""
Experiments Package - Run and Compare Baselines

Provides:
- ExperimentConfig: Configuration for experiments
- ExperimentRunner: Execute experiments across modes
- CLI for running all experiments
"""

from .config import (
    ExperimentConfig,
    ExperimentMode,
)
from .runner import (
    ExperimentRunner,
    ExperimentResult,
    run_experiment,
)

__all__ = [
    "ExperimentConfig",
    "ExperimentMode",
    "ExperimentRunner",
    "ExperimentResult",
    "run_experiment",
]
