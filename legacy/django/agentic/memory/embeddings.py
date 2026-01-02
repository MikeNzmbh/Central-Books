"""
Embedding Stores - Domain-Specific Embedding Models

Provides typed embedding stores for:
- Vendors: Company/vendor profiles
- Transactions: Transaction patterns and history
- Patterns: Audit/compliance patterns
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
from enum import Enum

from .vector_store import VectorStore, MemoryEntry, MemoryType, get_vector_store


# =============================================================================
# VENDOR EMBEDDINGS
# =============================================================================


@dataclass
class VendorEmbedding:
    """
    Vendor embedding for vendor matching and classification.
    
    Stores vendor information that can be used to:
    - Match new transactions to known vendors
    - Suggest expense categories
    - Detect vendor-related anomalies
    """
    
    vendor_id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    category_code: str = ""
    avg_transaction_amount: Decimal = Decimal("0")
    transaction_count: int = 0
    last_transaction_date: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_memory_entry(self, store: VectorStore) -> MemoryEntry:
        """Convert to a MemoryEntry for storage."""
        content = f"{self.name} {' '.join(self.aliases)}"
        
        return MemoryEntry(
            id=f"vendor-{self.vendor_id}",
            type=MemoryType.VENDOR,
            content=content,
            embedding=store._placeholder_embedding(content),
            metadata={
                "vendor_id": self.vendor_id,
                "name": self.name,
                "aliases": self.aliases,
                "category_code": self.category_code,
                "avg_transaction_amount": str(self.avg_transaction_amount),
                "transaction_count": self.transaction_count,
                "last_transaction_date": self.last_transaction_date,
                **self.metadata,
            },
        )


# =============================================================================
# TRANSACTION EMBEDDINGS
# =============================================================================


@dataclass
class TransactionEmbedding:
    """
    Transaction embedding for pattern matching.
    
    Stores transaction patterns that can be used to:
    - Classify new transactions
    - Detect unusual transaction patterns
    - Suggest account mappings
    """
    
    transaction_id: str
    description: str
    amount: Decimal
    category_code: str
    vendor_id: Optional[str] = None
    is_recurring: bool = False
    recurrence_pattern: str = ""  # "weekly", "monthly", etc.
    account_mapping: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_memory_entry(self, store: VectorStore) -> MemoryEntry:
        """Convert to a MemoryEntry for storage."""
        content = f"{self.description} {self.category_code}"
        
        return MemoryEntry(
            id=f"txn-{self.transaction_id}",
            type=MemoryType.TRANSACTION,
            content=content,
            embedding=store._placeholder_embedding(content),
            metadata={
                "transaction_id": self.transaction_id,
                "description": self.description,
                "amount": str(self.amount),
                "category_code": self.category_code,
                "vendor_id": self.vendor_id,
                "is_recurring": self.is_recurring,
                "recurrence_pattern": self.recurrence_pattern,
                "account_mapping": self.account_mapping,
                **self.metadata,
            },
        )


# =============================================================================
# PATTERN EMBEDDINGS
# =============================================================================


class PatternSeverity(str, Enum):
    """Severity levels for patterns."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PatternEmbedding:
    """
    Pattern embedding for audit/compliance pattern matching.
    
    Stores known patterns that can be used to:
    - Detect potential fraud or errors
    - Apply compliance rules
    - Flag unusual activity
    """
    
    pattern_id: str
    name: str
    description: str
    pattern_type: str  # "audit", "compliance", "risk"
    severity: PatternSeverity = PatternSeverity.MEDIUM
    indicators: List[str] = field(default_factory=list)
    detection_rules: Dict[str, Any] = field(default_factory=dict)
    recommended_action: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_memory_entry(self, store: VectorStore) -> MemoryEntry:
        """Convert to a MemoryEntry for storage."""
        content = f"{self.name} {self.description} {' '.join(self.indicators)}"
        
        # Determine memory type
        if self.pattern_type == "audit":
            mem_type = MemoryType.AUDIT_PATTERN
        elif self.pattern_type == "compliance":
            mem_type = MemoryType.COMPLIANCE_RULE
        else:
            mem_type = MemoryType.RISK_SIGNATURE
        
        return MemoryEntry(
            id=f"pattern-{self.pattern_id}",
            type=mem_type,
            content=content,
            embedding=store._placeholder_embedding(content),
            metadata={
                "pattern_id": self.pattern_id,
                "name": self.name,
                "description": self.description,
                "pattern_type": self.pattern_type,
                "severity": self.severity.value,
                "indicators": self.indicators,
                "detection_rules": self.detection_rules,
                "recommended_action": self.recommended_action,
                **self.metadata,
            },
            relevance_score=self._severity_to_relevance(),
        )
    
    def _severity_to_relevance(self) -> float:
        """Convert severity to relevance boost."""
        severity_map = {
            PatternSeverity.INFO: 0.5,
            PatternSeverity.LOW: 0.75,
            PatternSeverity.MEDIUM: 1.0,
            PatternSeverity.HIGH: 1.25,
            PatternSeverity.CRITICAL: 1.5,
        }
        return severity_map.get(self.severity, 1.0)


# =============================================================================
# EMBEDDING STORE
# =============================================================================


class EmbeddingStore:
    """
    High-level interface for managing domain-specific embeddings.
    
    Wraps VectorStore with typed accessors for vendors, transactions,
    and patterns.
    """
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self._store = vector_store or get_vector_store()
    
    @property
    def store(self) -> VectorStore:
        return self._store
    
    # =========================================================================
    # VENDOR METHODS
    # =========================================================================
    
    def add_vendor(self, vendor: VendorEmbedding) -> str:
        """Add a vendor embedding."""
        entry = vendor.to_memory_entry(self._store)
        return self._store.add(entry)
    
    def find_vendor(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find vendors matching a query."""
        results = self._store.search_by_text(
            query,
            memory_type=MemoryType.VENDOR,
            top_k=top_k,
        )
        return [
            {"vendor": entry.metadata, "similarity": sim}
            for entry, sim in results
        ]
    
    def get_all_vendors(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all vendor embeddings."""
        entries = self._store.list_by_type(MemoryType.VENDOR, limit)
        return [entry.metadata for entry in entries]
    
    # =========================================================================
    # TRANSACTION METHODS
    # =========================================================================
    
    def add_transaction(self, txn: TransactionEmbedding) -> str:
        """Add a transaction embedding."""
        entry = txn.to_memory_entry(self._store)
        return self._store.add(entry)
    
    def find_similar_transactions(
        self,
        description: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find transactions similar to a description."""
        results = self._store.search_by_text(
            description,
            memory_type=MemoryType.TRANSACTION,
            top_k=top_k,
        )
        return [
            {"transaction": entry.metadata, "similarity": sim}
            for entry, sim in results
        ]
    
    # =========================================================================
    # PATTERN METHODS
    # =========================================================================
    
    def add_pattern(self, pattern: PatternEmbedding) -> str:
        """Add a pattern embedding."""
        entry = pattern.to_memory_entry(self._store)
        return self._store.add(entry)
    
    def find_matching_patterns(
        self,
        context: str,
        pattern_types: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find patterns matching a context."""
        # Search across all pattern types
        all_results = []
        
        for mem_type in [MemoryType.AUDIT_PATTERN, MemoryType.COMPLIANCE_RULE, MemoryType.RISK_SIGNATURE]:
            results = self._store.search_by_text(
                context,
                memory_type=mem_type,
                top_k=top_k,
            )
            
            for entry, sim in results:
                if pattern_types is None or entry.metadata.get("pattern_type") in pattern_types:
                    all_results.append({
                        "pattern": entry.metadata,
                        "similarity": sim,
                    })
        
        # Sort by similarity
        all_results.sort(key=lambda x: x["similarity"], reverse=True)
        return all_results[:top_k]
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    def seed_demo_data(self) -> int:
        """Seed the store with demo data."""
        count = 0
        
        # Demo vendors
        vendors = [
            VendorEmbedding(
                vendor_id="v-001",
                name="Office Depot",
                aliases=["OfficeMax", "OD"],
                category_code="6100",
                avg_transaction_amount=Decimal("89.99"),
            ),
            VendorEmbedding(
                vendor_id="v-002",
                name="Amazon Web Services",
                aliases=["AWS", "Amazon"],
                category_code="6300",
                avg_transaction_amount=Decimal("250.00"),
            ),
            VendorEmbedding(
                vendor_id="v-003",
                name="Starbucks",
                aliases=["SBUX"],
                category_code="6200",
                avg_transaction_amount=Decimal("15.00"),
            ),
        ]
        
        for vendor in vendors:
            self.add_vendor(vendor)
            count += 1
        
        # Demo patterns
        patterns = [
            PatternEmbedding(
                pattern_id="p-001",
                name="Unusual Transaction Scale",
                description="Transaction amount significantly higher than average",
                pattern_type="audit",
                severity=PatternSeverity.MEDIUM,
                indicators=["amount_spike", "3x_average"],
            ),
            PatternEmbedding(
                pattern_id="p-002",
                name="Suspense Account Usage",
                description="Transaction posted to suspense or uncategorized account",
                pattern_type="audit",
                severity=PatternSeverity.LOW,
                indicators=["suspense", "uncategorized", "other_misc"],
            ),
            PatternEmbedding(
                pattern_id="p-003",
                name="Currency Mismatch",
                description="Transaction currency differs from account default",
                pattern_type="compliance",
                severity=PatternSeverity.MEDIUM,
                indicators=["currency", "forex"],
            ),
        ]
        
        for pattern in patterns:
            self.add_pattern(pattern)
            count += 1
        
        return count
