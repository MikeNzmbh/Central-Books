from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    needs_password_reset: Mapped[bool] = mapped_column(Boolean, default=False)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    businesses: Mapped[list["Business"]] = relationship("Business", back_populates="owner")


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    plan: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="businesses")
    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="business")
    suppliers: Mapped[list["Supplier"]] = relationship("Supplier", back_populates="business")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="business")
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="business")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="business")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="customers")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="customer")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), default="")
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="suppliers")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # ASSET/LIABILITY/EQUITY/INCOME/EXPENSE
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="accounts")
    parent: Mapped["Account | None"] = relationship("Account", remote_side=[id])
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="account")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(10), default="EXPENSE")  # INCOME/EXPENSE
    code: Mapped[str] = mapped_column(String(32), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="categories")
    account: Mapped["Account | None"] = relationship("Account", back_populates="categories")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="DRAFT")  # DRAFT/SENT/PARTIAL/PAID/VOID
    description: Mapped[str] = mapped_column(Text, default="")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    net_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="invoices")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="invoices")


class ImportMap(Base):
    """Tracks legacy records imported to prevent duplicates."""
    __tablename__ = "import_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    legacy_table: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    legacy_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    new_table: Mapped[str] = mapped_column(String(100), nullable=False)
    new_pk: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
