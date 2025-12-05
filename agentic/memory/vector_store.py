"""
Vector Store - In-Memory Vector Storage for Agent Memory

Provides:
- MemoryEntry: Structured memory with embeddings
- VectorStore: Storage and retrieval of memory entries
- Similarity search for relevant memories

Note: This is a placeholder implementation using in-memory storage.
For production, integrate with ChromaDB, Pinecone, or similar.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
import math


# =============================================================================
# ENUMS
# =============================================================================


class MemoryType(str, Enum):
    """Types of memory entries."""
    
    VENDOR = "vendor"                    # Vendor information
    TRANSACTION = "transaction"          # Transaction patterns
    AUDIT_PATTERN = "audit_pattern"      # Audit findings/patterns
    COMPLIANCE_RULE = "compliance_rule"  # Compliance rules
    USER_PREFERENCE = "user_preference"  # User behavior preferences
    RISK_SIGNATURE = "risk_signature"    # Known risk patterns
    WORKFLOW_OUTCOME = "workflow_outcome"  # Past workflow results


# =============================================================================
# MEMORY ENTRY MODEL
# =============================================================================


@dataclass
class MemoryEntry:
    """
    A single memory entry with embedding.
    
    Attributes:
        id: Unique identifier
        type: Memory type category
        content: Textual content
        embedding: Vector representation (list of floats)
        metadata: Additional structured data
        created_at: When memory was created
        accessed_at: When memory was last retrieved
        access_count: Number of times retrieved
        relevance_score: Base relevance (can be boosted)
    """
    
    id: str = field(default_factory=lambda: f"mem-{uuid4().hex[:12]}")
    type: MemoryType = MemoryType.TRANSACTION
    content: str = ""
    embedding: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    accessed_at: Optional[datetime] = None
    access_count: int = 0
    relevance_score: float = 1.0
    
    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "embedding_dim": len(self.embedding),  # Don't serialize full embedding
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "access_count": self.access_count,
            "relevance_score": self.relevance_score,
        }
    
    def mark_accessed(self) -> None:
        """Update access tracking."""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1


# =============================================================================
# VECTOR STORE
# =============================================================================


class VectorStore:
    """
    In-memory vector store for agent memory.
    
    Provides:
    - Add/update/delete memories
    - Similarity search via cosine similarity
    - Type-based filtering
    - Relevance boosting
    
    Note: This uses pure Python for demo purposes.
    Production should use numpy/faiss/chromadb.
    """
    
    def __init__(self, embedding_dim: int = 384):
        self._memories: Dict[str, MemoryEntry] = {}
        self._embedding_dim = embedding_dim
        self._type_index: Dict[MemoryType, set] = {t: set() for t in MemoryType}
    
    @property
    def size(self) -> int:
        """Number of memories stored."""
        return len(self._memories)
    
    @property
    def embedding_dim(self) -> int:
        """Dimension of embeddings."""
        return self._embedding_dim
    
    def add(self, entry: MemoryEntry) -> str:
        """
        Add a memory entry.
        
        Returns the entry ID.
        """
        # Validate embedding dimension
        if entry.embedding and len(entry.embedding) != self._embedding_dim:
            # Pad or truncate
            if len(entry.embedding) < self._embedding_dim:
                entry.embedding.extend([0.0] * (self._embedding_dim - len(entry.embedding)))
            else:
                entry.embedding = entry.embedding[:self._embedding_dim]
        elif not entry.embedding:
            # Generate placeholder embedding
            entry.embedding = self._placeholder_embedding(entry.content)
        
        self._memories[entry.id] = entry
        self._type_index[entry.type].add(entry.id)
        
        return entry.id
    
    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        entry = self._memories.get(memory_id)
        if entry:
            entry.mark_accessed()
        return entry
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        entry = self._memories.pop(memory_id, None)
        if entry:
            self._type_index[entry.type].discard(memory_id)
            return True
        return False
    
    def update(self, memory_id: str, **updates) -> Optional[MemoryEntry]:
        """Update a memory's fields."""
        entry = self._memories.get(memory_id)
        if not entry:
            return None
        
        for key, value in updates.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        
        return entry
    
    def search(
        self,
        query_embedding: List[float],
        memory_type: Optional[MemoryType] = None,
        top_k: int = 10,
        min_similarity: float = 0.0,
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Search for similar memories.
        
        Args:
            query_embedding: Query vector
            memory_type: Optional filter by type
            top_k: Maximum results to return
            min_similarity: Minimum similarity threshold
        
        Returns:
            List of (entry, similarity) tuples, sorted by similarity desc.
        """
        # Validate query
        if len(query_embedding) != self._embedding_dim:
            query_embedding = self._pad_embedding(query_embedding)
        
        # Get candidate IDs
        if memory_type:
            candidate_ids = self._type_index[memory_type]
        else:
            candidate_ids = set(self._memories.keys())
        
        # Compute similarities
        results = []
        for mem_id in candidate_ids:
            entry = self._memories[mem_id]
            sim = self._cosine_similarity(query_embedding, entry.embedding)
            
            # Apply relevance boost
            sim *= entry.relevance_score
            
            if sim >= min_similarity:
                results.append((entry, sim))
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Mark accessed
        for entry, _ in results[:top_k]:
            entry.mark_accessed()
        
        return results[:top_k]
    
    def search_by_text(
        self,
        query_text: str,
        memory_type: Optional[MemoryType] = None,
        top_k: int = 10,
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Search using text (generates placeholder embedding).
        
        In production, this would call an embedding model.
        """
        query_embedding = self._placeholder_embedding(query_text)
        return self.search(query_embedding, memory_type, top_k)
    
    def list_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
    ) -> List[MemoryEntry]:
        """List memories of a specific type."""
        ids = list(self._type_index[memory_type])[:limit]
        return [self._memories[mid] for mid in ids if mid in self._memories]
    
    def clear(self) -> int:
        """Clear all memories. Returns count deleted."""
        count = len(self._memories)
        self._memories.clear()
        for mem_type in self._type_index:
            self._type_index[mem_type].clear()
        return count
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _placeholder_embedding(self, text: str) -> List[float]:
        """
        Generate a placeholder embedding from text.
        
        In production, this would call an embedding model (e.g., OpenAI, Sentence-BERT).
        For demo purposes, we use a simple hash-based approach.
        """
        # Simple deterministic "embedding" based on text hash
        embedding = [0.0] * self._embedding_dim
        
        if not text:
            return embedding
        
        # Create pseudo-random values from text
        for i, char in enumerate(text):
            idx = (ord(char) + i) % self._embedding_dim
            embedding[idx] += 0.1
        
        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    
    def _pad_embedding(self, embedding: List[float]) -> List[float]:
        """Pad or truncate embedding to target dimension."""
        if len(embedding) < self._embedding_dim:
            return embedding + [0.0] * (self._embedding_dim - len(embedding))
        return embedding[:self._embedding_dim]


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================


_default_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the default vector store."""
    global _default_store
    if _default_store is None:
        _default_store = VectorStore()
    return _default_store
