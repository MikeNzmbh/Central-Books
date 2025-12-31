"""
Vector Store - FAISS-backed Vector Storage for Agent Memory
Compatible with existing MemoryEntry and MemoryType.
"""

import os
import pickle
import numpy as np
import faiss
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from sentence_transformers import SentenceTransformer

# =============================================================================
# ENUMS
# =============================================================================

class MemoryType(str, Enum):
    """Types of memory entries."""
    VENDOR = "vendor"
    TRANSACTION = "transaction"
    AUDIT_PATTERN = "audit_pattern"
    COMPLIANCE_RULE = "compliance_rule"
    USER_PREFERENCE = "user_preference"
    RISK_SIGNATURE = "risk_signature"
    WORKFLOW_OUTCOME = "workflow_outcome"

# =============================================================================
# MEMORY ENTRY MODEL
# =============================================================================

@dataclass
class MemoryEntry:
    """A single memory entry with embedding."""
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
            "embedding_dim": len(self.embedding),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "access_count": self.access_count,
            "relevance_score": self.relevance_score,
        }
    
    def mark_accessed(self) -> None:
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1

# =============================================================================
# VECTOR STORE
# =============================================================================

class VectorStore:
    """
    FAISS-backed vector store for agent memory.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", store_path: str = "agentic/memory/faiss_store.pkl"):
        self.model = SentenceTransformer(model_name)
        self._embedding_dim = self.model.get_sentence_embedding_dimension()
        self.store_path = store_path
        
        # FAISS index
        self.index = faiss.IndexFlatL2(self._embedding_dim)
        # Store for MemoryEntry objects
        self._memories: Dict[str, MemoryEntry] = {}
        # Mapping from FAISS index position to memory_id
        self._pos_to_id: List[str] = []
        self._type_index: Dict[MemoryType, set] = {t: set() for t in MemoryType}
        
        if os.path.exists(self.store_path):
            self.load()

    @property
    def size(self) -> int:
        return len(self._memories)

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def add(self, entry: MemoryEntry) -> str:
        """Add a memory entry."""
        if not entry.embedding:
            entry.embedding = self.model.encode([entry.content])[0].tolist()
        
        embedding = np.array([entry.embedding]).astype('float32')
        self.index.add(embedding)
        
        self._memories[entry.id] = entry
        self._pos_to_id.append(entry.id)
        self._type_index[entry.type].add(entry.id)
        
        self.save()
        return entry.id

    def search(
        self,
        query_embedding: List[float],
        memory_type: Optional[MemoryType] = None,
        top_k: int = 10,
        min_similarity: float = 0.0,
    ) -> List[Tuple[MemoryEntry, float]]:
        """Search similar memories."""
        if self.index.ntotal == 0:
            return []
            
        embedding = np.array([query_embedding]).astype('float32')
        distances, indices = self.index.search(embedding, top_k * 2) # Get more for filtering
        
        results = []
        for d, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self._pos_to_id):
                continue
            
            mem_id = self._pos_to_id[idx]
            entry = self._memories[mem_id]
            
            if memory_type and entry.type != memory_type:
                continue
                
            # FAISS L2 distance: lower is better. 
            # We convert to a 'similarity' score for compatibility
            sim = 1.0 / (1.0 + float(d))
            sim *= entry.relevance_score
            
            if sim >= min_similarity:
                entry.mark_accessed()
                results.append((entry, sim))
                
        return results[:top_k]

    def search_by_text(
        self,
        query_text: str,
        memory_type: Optional[MemoryType] = None,
        top_k: int = 10,
    ) -> List[Tuple[MemoryEntry, float]]:
        query_embedding = self.model.encode([query_text])[0].tolist()
        return self.search(query_embedding, memory_type, top_k)

    def list_by_type(self, memory_type: MemoryType, limit: int = 100) -> List[MemoryEntry]:
        ids = list(self._type_index[memory_type])[:limit]
        return [self._memories[mid] for mid in ids if mid in self._memories]

    def save(self) -> None:
        try:
            with open(self.store_path, "wb") as f:
                pickle.dump({
                    "memories": self._memories,
                    "pos_to_id": self._pos_to_id,
                    "type_index": self._type_index,
                    "index": faiss.serialize_index(self.index)
                }, f)
        except Exception as e:
            print(f"Error saving store: {e}")

    def load(self) -> None:
        try:
            with open(self.store_path, "rb") as f:
                data = pickle.load(f)
                self._memories = data["memories"]
                self._pos_to_id = data["pos_to_id"]
                self._type_index = data["type_index"]
                self.index = faiss.deserialize_index(data["index"])
        except Exception as e:
            print(f"Error loading store: {e}")

    def _placeholder_embedding(self, text: str) -> List[float]:
        """Compatibility method."""
        return self.model.encode([text])[0].tolist()

_default_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    global _default_store
    if _default_store is None:
        _default_store = VectorStore()
    return _default_store
