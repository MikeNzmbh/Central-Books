"""
Retrieval API - Query Interface for Agent Memory

Provides:
- RetrievalAPI: Unified interface for memory queries
- RetrievalResult: Structured query results
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .vector_store import VectorStore, MemoryEntry, MemoryType, get_vector_store
from .embeddings import EmbeddingStore


# =============================================================================
# RESULT MODELS
# =============================================================================


class RetrievalStrategy(str, Enum):
    """Retrieval strategy options."""
    SIMILARITY = "similarity"      # Pure vector similarity
    RECENCY = "recency"            # Prefer recent memories
    FREQUENCY = "frequency"        # Prefer frequently accessed
    HYBRID = "hybrid"              # Combine all factors


@dataclass
class RetrievalResult:
    """
    Result from a memory retrieval query.
    
    Attributes:
        query: Original query text
        results: List of matching memories with scores
        total_found: Total matches before limit
        strategy: Strategy used for retrieval
        latency_ms: Query execution time
    """
    
    query: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    total_found: int = 0
    strategy: RetrievalStrategy = RetrievalStrategy.SIMILARITY
    latency_ms: float = 0.0
    
    def model_dump(self) -> dict:
        return {
            "query": self.query,
            "results": self.results,
            "total_found": self.total_found,
            "strategy": self.strategy.value,
            "latency_ms": self.latency_ms,
        }
    
    @property
    def top_result(self) -> Optional[Dict[str, Any]]:
        """Get the top result if any."""
        return self.results[0] if self.results else None
    
    @property
    def is_empty(self) -> bool:
        """Check if no results found."""
        return len(self.results) == 0


# =============================================================================
# RETRIEVAL API
# =============================================================================


class RetrievalAPI:
    """
    Unified interface for querying agent memory.
    
    Supports:
    - Text-based similarity search
    - Type-filtered queries
    - Multiple retrieval strategies
    - Context-aware retrieval
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_store: Optional[EmbeddingStore] = None,
    ):
        self._store = vector_store or get_vector_store()
        self._embedding_store = embedding_store or EmbeddingStore(self._store)
    
    @property
    def store(self) -> VectorStore:
        return self._store
    
    @property
    def embeddings(self) -> EmbeddingStore:
        return self._embedding_store
    
    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    
    def query(
        self,
        text: str,
        memory_type: Optional[MemoryType] = None,
        strategy: RetrievalStrategy = RetrievalStrategy.SIMILARITY,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> RetrievalResult:
        """
        Query memory with text.
        
        Args:
            text: Query text
            memory_type: Optional filter by type
            strategy: Retrieval strategy
            top_k: Maximum results
            min_score: Minimum similarity threshold
        
        Returns:
            RetrievalResult with matching memories
        """
        start_time = datetime.now(timezone.utc)
        
        # Get raw results from vector store
        raw_results = self._store.search_by_text(
            text,
            memory_type=memory_type,
            top_k=top_k * 2,  # Get more for reranking
        )
        
        # Apply strategy
        if strategy == RetrievalStrategy.RECENCY:
            raw_results = self._rerank_by_recency(raw_results)
        elif strategy == RetrievalStrategy.FREQUENCY:
            raw_results = self._rerank_by_frequency(raw_results)
        elif strategy == RetrievalStrategy.HYBRID:
            raw_results = self._rerank_hybrid(raw_results)
        
        # Filter by min score and limit
        filtered = [
            (entry, score)
            for entry, score in raw_results
            if score >= min_score
        ][:top_k]
        
        # Build results
        results = [
            {
                "id": entry.id,
                "type": entry.type.value,
                "content": entry.content,
                "score": score,
                "metadata": entry.metadata,
            }
            for entry, score in filtered
        ]
        
        end_time = datetime.now(timezone.utc)
        latency = (end_time - start_time).total_seconds() * 1000
        
        return RetrievalResult(
            query=text,
            results=results,
            total_found=len(raw_results),
            strategy=strategy,
            latency_ms=latency,
        )
    
    def query_vendors(
        self,
        query: str,
        top_k: int = 5,
    ) -> RetrievalResult:
        """Query for matching vendors."""
        return self.query(
            query,
            memory_type=MemoryType.VENDOR,
            top_k=top_k,
        )
    
    def query_patterns(
        self,
        context: str,
        pattern_types: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        """Query for matching audit/compliance patterns."""
        # Query across all pattern types
        all_results = []
        
        for mem_type in [MemoryType.AUDIT_PATTERN, MemoryType.COMPLIANCE_RULE, MemoryType.RISK_SIGNATURE]:
            result = self.query(
                context,
                memory_type=mem_type,
                top_k=top_k,
            )
            all_results.extend(result.results)
        
        # Filter by pattern type if specified
        if pattern_types:
            all_results = [
                r for r in all_results
                if r.get("metadata", {}).get("pattern_type") in pattern_types
            ]
        
        # Sort and limit
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_results = all_results[:top_k]
        
        return RetrievalResult(
            query=context,
            results=all_results,
            total_found=len(all_results),
            strategy=RetrievalStrategy.SIMILARITY,
        )
    
    def get_recent_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Get most recently accessed memories."""
        if memory_type:
            entries = self._store.list_by_type(memory_type, limit=limit * 2)
        else:
            entries = list(self._store._memories.values())
        
        # Sort by access time
        entries = [e for e in entries if e.accessed_at]
        entries.sort(key=lambda x: x.accessed_at, reverse=True)
        
        return entries[:limit]
    
    def get_frequent_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Get most frequently accessed memories."""
        if memory_type:
            entries = self._store.list_by_type(memory_type, limit=limit * 2)
        else:
            entries = list(self._store._memories.values())
        
        # Sort by access count
        entries.sort(key=lambda x: x.access_count, reverse=True)
        
        return entries[:limit]
    
    # =========================================================================
    # CONTEXT-AWARE QUERIES
    # =========================================================================
    
    def get_context_for_transaction(
        self,
        description: str,
        amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Get relevant context for processing a transaction.
        
        Returns vendor suggestions, similar transactions, and applicable patterns.
        """
        context = {
            "vendors": [],
            "similar_transactions": [],
            "patterns": [],
        }
        
        # Find matching vendors
        vendor_result = self.query_vendors(description, top_k=3)
        context["vendors"] = vendor_result.results
        
        # Find similar transactions
        txn_result = self.query(description, memory_type=MemoryType.TRANSACTION, top_k=3)
        context["similar_transactions"] = txn_result.results
        
        # Find applicable patterns
        pattern_result = self.query_patterns(description, top_k=3)
        context["patterns"] = pattern_result.results
        
        return context
    
    # =========================================================================
    # RERANKING STRATEGIES
    # =========================================================================
    
    def _rerank_by_recency(
        self,
        results: List[tuple],
    ) -> List[tuple]:
        """Rerank results to boost recent memories."""
        now = datetime.now(timezone.utc)
        
        def recency_score(entry: MemoryEntry) -> float:
            if not entry.accessed_at:
                return 0.0
            age_hours = (now - entry.accessed_at).total_seconds() / 3600
            return 1.0 / (1.0 + age_hours)  # Decay with age
        
        reranked = [
            (entry, score * 0.7 + recency_score(entry) * 0.3)
            for entry, score in results
        ]
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
    
    def _rerank_by_frequency(
        self,
        results: List[tuple],
    ) -> List[tuple]:
        """Rerank results to boost frequently accessed memories."""
        max_count = max((e.access_count for e, _ in results), default=1)
        if max_count == 0:
            max_count = 1
        
        reranked = [
            (entry, score * 0.7 + (entry.access_count / max_count) * 0.3)
            for entry, score in results
        ]
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
    
    def _rerank_hybrid(
        self,
        results: List[tuple],
    ) -> List[tuple]:
        """Combine similarity, recency, and frequency."""
        now = datetime.now(timezone.utc)
        max_count = max((e.access_count for e, _ in results), default=1)
        if max_count == 0:
            max_count = 1
        
        def hybrid_score(entry: MemoryEntry, sim_score: float) -> float:
            # Recency component
            recency = 0.0
            if entry.accessed_at:
                age_hours = (now - entry.accessed_at).total_seconds() / 3600
                recency = 1.0 / (1.0 + age_hours)
            
            # Frequency component
            frequency = entry.access_count / max_count
            
            # Combined: 60% similarity, 20% recency, 20% frequency
            return sim_score * 0.6 + recency * 0.2 + frequency * 0.2
        
        reranked = [
            (entry, hybrid_score(entry, score))
            for entry, score in results
        ]
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================


_default_api: Optional[RetrievalAPI] = None


def get_retrieval_api() -> RetrievalAPI:
    """Get or create the default retrieval API."""
    global _default_api
    if _default_api is None:
        _default_api = RetrievalAPI()
    return _default_api
