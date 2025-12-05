"""
Memory package for long-term agent memory.

Provides:
- VectorStore: In-memory vector storage (placeholder for real vector DB)
- EmbeddingStore: Stores domain-specific embeddings
- RetrievalAPI: Query interface for memory retrieval
"""

from .vector_store import (
    VectorStore,
    MemoryEntry,
    MemoryType,
)
from .embeddings import (
    EmbeddingStore,
    VendorEmbedding,
    TransactionEmbedding,
    PatternEmbedding,
)
from .retrieval import (
    RetrievalAPI,
    RetrievalResult,
)

__all__ = [
    "VectorStore",
    "MemoryEntry",
    "MemoryType",
    "EmbeddingStore",
    "VendorEmbedding",
    "TransactionEmbedding",
    "PatternEmbedding",
    "RetrievalAPI",
    "RetrievalResult",
]
