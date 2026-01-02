"""
Agentic System Root Package

This package contains the full multi-agent accounting system infrastructure:

- engine/: LLM accounting pipeline (ingestion → normalization → entry generation → audit)
- agents/: Role-based agents (operations, support, sales, engineering, data integrity)
- workflows/: Workflow graph orchestration
- memory/: Vector store and RAG modules
- interfaces/: API, consumers, and CLI
- logging/: Tracing and event logging

This is scaffolding for the OpenAI Residency build. No active execution yet.
"""

__version__ = "0.1.0"
__author__ = "Clover Books / CloverBooks Team"

# Package will export key components once implemented
__all__ = [
    "__version__",
]
