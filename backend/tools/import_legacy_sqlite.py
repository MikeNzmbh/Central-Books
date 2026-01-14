#!/usr/bin/env python
"""
Legacy Django SQLite Import Tool for Clover Books Option B

Usage:
  python tools/import_legacy_sqlite.py --legacy-db /path/to/db.sqlite3 --mode dry-run
  python tools/import_legacy_sqlite.py --legacy-db /path/to/db.sqlite3 --mode import
  python tools/import_legacy_sqlite.py --legacy-db /path/to/db.sqlite3 --mode verify
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_val(row, key, default=None):
    """Safely get value from sqlite3.Row."""
    try:
        return row[key] if row[key] is not None else default
    except (IndexError, KeyError):
        return default


def get_legacy_connection(db_path: str) -> sqlite3.Connection:
    """Open connection to legacy SQLite database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Legacy database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def count_legacy_tables(conn: sqlite3.Connection) -> dict[str, int]:
    """Count records in each migrating table."""
    tables = [
        "auth_user",
        "core_business", 
        "core_customer",
        "core_supplier",
        "core_account",
        "core_category",
        "core_invoice",
    ]
    counts = {}
    for table in tables:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = 0
    return counts


def dry_run(legacy_db: str) -> dict:
    """Report what would be imported without making changes."""
    conn = get_legacy_connection(legacy_db)
    counts = count_legacy_tables(conn)
    conn.close()
    
    report = {
        "mode": "dry-run",
        "legacy_db": legacy_db,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tables": counts,
        "total_records": sum(counts.values()),
    }
    
    print("\n=== DRY RUN REPORT ===")
    print(f"Legacy DB: {legacy_db}")
    print(f"Timestamp: {report['timestamp']}")
    print("\nTable Counts:")
    for table, count in counts.items():
        new_table = table.replace("auth_", "").replace("core_", "") + "s"
        if table == "auth_user":
            new_table = "users"
        print(f"  {table} → {new_table}: {count} records")
    print(f"\nTotal: {report['total_records']} records to migrate")
    
    return report


def import_data(legacy_db: str, target_db_url: str) -> dict:
    """Import data from legacy DB to new DB."""
    from app.models import User, Business, Customer, Supplier, Account, Category, Invoice, ImportMap
    from app.db import Base
    
    engine = create_engine(target_db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    
    legacy_conn = get_legacy_connection(legacy_db)
    
    report = {
        "mode": "import",
        "legacy_db": legacy_db,
        "target_db": target_db_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": {},
    }
    
    with Session() as session:
        # 1. Import Users
        print("\n[1/7] Importing users...")
        users_imported = 0
        legacy_to_new_user: dict[int, int] = {}
        
        for row in legacy_conn.execute("SELECT * FROM auth_user"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="auth_user", legacy_pk=legacy_id
            ).first()
            if existing:
                legacy_to_new_user[legacy_id] = existing.new_pk
                continue
                
            if session.query(User).filter_by(email=row["email"]).first():
                continue
            
            first_name = get_val(row, "first_name", "")
            last_name = get_val(row, "last_name", "")
            name = f"{first_name} {last_name}".strip() or None
            user = User(
                email=row["email"],
                name=name,
                password_hash=row["password"],
                is_admin=bool(row["is_superuser"]),
                is_active=bool(row["is_active"]),
                needs_password_reset=True,
                legacy_id=legacy_id,
            )
            session.add(user)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="auth_user",
                legacy_pk=legacy_id,
                new_table="users",
                new_pk=user.id,
            ))
            legacy_to_new_user[legacy_id] = user.id
            users_imported += 1
        
        session.commit()
        report["results"]["users"] = {"imported": users_imported}
        print(f"  ✓ {users_imported} users imported")
        
        # 2. Import Businesses  
        print("\n[2/7] Importing businesses...")
        businesses_imported = 0
        legacy_to_new_business: dict[int, int] = {}
        
        for row in legacy_conn.execute("SELECT * FROM core_business"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_business", legacy_pk=legacy_id
            ).first()
            if existing:
                legacy_to_new_business[legacy_id] = existing.new_pk
                continue
            
            owner_user_id = legacy_to_new_user.get(row["owner_user_id"])
            if not owner_user_id:
                print(f"  ⚠ Skipping business {row['name']}: owner not found")
                continue
                
            if session.query(Business).filter_by(name=row["name"]).first():
                continue
            
            # Check for ai_companion_enabled column
            try:
                ai_enabled = bool(row["ai_companion_enabled"])
            except (IndexError, KeyError):
                ai_enabled = False
            
            business = Business(
                name=row["name"],
                currency=get_val(row, "currency", "CAD"),
                owner_user_id=owner_user_id,
                plan=get_val(row, "plan", ""),
                status=get_val(row, "status", "active"),
                ai_enabled=ai_enabled,
                legacy_id=legacy_id,
            )
            session.add(business)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_business",
                legacy_pk=legacy_id,
                new_table="businesses",
                new_pk=business.id,
            ))
            legacy_to_new_business[legacy_id] = business.id
            businesses_imported += 1
        
        session.commit()
        report["results"]["businesses"] = {"imported": businesses_imported}
        print(f"  ✓ {businesses_imported} businesses imported")
        
        # 3. Import Customers
        print("\n[3/7] Importing customers...")
        customers_imported = 0
        legacy_to_new_customer: dict[int, int] = {}
        
        for row in legacy_conn.execute("SELECT * FROM core_customer"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_customer", legacy_pk=legacy_id
            ).first()
            if existing:
                legacy_to_new_customer[legacy_id] = existing.new_pk
                continue
            
            business_id = legacy_to_new_business.get(row["business_id"])
            if not business_id:
                continue
            
            customer = Customer(
                business_id=business_id,
                name=row["name"],
                email=get_val(row, "email"),
                phone=get_val(row, "phone", ""),
                is_active=bool(get_val(row, "is_active", True)),
                legacy_id=legacy_id,
            )
            session.add(customer)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_customer",
                legacy_pk=legacy_id,
                new_table="customers",
                new_pk=customer.id,
            ))
            legacy_to_new_customer[legacy_id] = customer.id
            customers_imported += 1
        
        session.commit()
        report["results"]["customers"] = {"imported": customers_imported}
        print(f"  ✓ {customers_imported} customers imported")
        
        # 4. Import Suppliers
        print("\n[4/7] Importing suppliers...")
        suppliers_imported = 0
        
        for row in legacy_conn.execute("SELECT * FROM core_supplier"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_supplier", legacy_pk=legacy_id
            ).first()
            if existing:
                continue
            
            business_id = legacy_to_new_business.get(row["business_id"])
            if not business_id:
                continue
            
            supplier = Supplier(
                business_id=business_id,
                name=row["name"],
                email=get_val(row, "email"),
                phone=get_val(row, "phone", ""),
                legacy_id=legacy_id,
            )
            session.add(supplier)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_supplier",
                legacy_pk=legacy_id,
                new_table="suppliers",
                new_pk=supplier.id,
            ))
            suppliers_imported += 1
        
        session.commit()
        report["results"]["suppliers"] = {"imported": suppliers_imported}
        print(f"  ✓ {suppliers_imported} suppliers imported")
        
        # 5. Import Accounts
        print("\n[5/7] Importing accounts...")
        accounts_imported = 0
        legacy_to_new_account: dict[int, int] = {}
        
        # First pass: accounts without parents
        for row in legacy_conn.execute("SELECT * FROM core_account WHERE parent_id IS NULL"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_account", legacy_pk=legacy_id
            ).first()
            if existing:
                legacy_to_new_account[legacy_id] = existing.new_pk
                continue
            
            business_id = legacy_to_new_business.get(row["business_id"])
            if not business_id:
                continue
            
            account = Account(
                business_id=business_id,
                code=get_val(row, "code", ""),
                name=row["name"],
                type=row["type"],
                is_active=bool(get_val(row, "is_active", True)),
                description=get_val(row, "description", ""),
                legacy_id=legacy_id,
            )
            session.add(account)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_account",
                legacy_pk=legacy_id,
                new_table="accounts",
                new_pk=account.id,
            ))
            legacy_to_new_account[legacy_id] = account.id
            accounts_imported += 1
        
        session.commit()
        
        # Second pass: accounts with parents
        for row in legacy_conn.execute("SELECT * FROM core_account WHERE parent_id IS NOT NULL"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_account", legacy_pk=legacy_id
            ).first()
            if existing:
                legacy_to_new_account[legacy_id] = existing.new_pk
                continue
            
            business_id = legacy_to_new_business.get(row["business_id"])
            parent_id = legacy_to_new_account.get(row["parent_id"])
            if not business_id:
                continue
            
            account = Account(
                business_id=business_id,
                code=get_val(row, "code", ""),
                name=row["name"],
                type=row["type"],
                parent_id=parent_id,
                is_active=bool(get_val(row, "is_active", True)),
                description=get_val(row, "description", ""),
                legacy_id=legacy_id,
            )
            session.add(account)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_account",
                legacy_pk=legacy_id,
                new_table="accounts",
                new_pk=account.id,
            ))
            legacy_to_new_account[legacy_id] = account.id
            accounts_imported += 1
        
        session.commit()
        report["results"]["accounts"] = {"imported": accounts_imported}
        print(f"  ✓ {accounts_imported} accounts imported")
        
        # 6. Import Categories
        print("\n[6/7] Importing categories...")
        categories_imported = 0
        
        for row in legacy_conn.execute("SELECT * FROM core_category"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_category", legacy_pk=legacy_id
            ).first()
            if existing:
                continue
            
            business_id = legacy_to_new_business.get(row["business_id"])
            account_id = legacy_to_new_account.get(get_val(row, "account_id"))
            if not business_id:
                continue
            
            category = Category(
                business_id=business_id,
                name=row["name"],
                type=get_val(row, "type", "EXPENSE"),
                code=get_val(row, "code", ""),
                description=get_val(row, "description", ""),
                account_id=account_id,
                is_archived=bool(get_val(row, "is_archived", False)),
                legacy_id=legacy_id,
            )
            session.add(category)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_category",
                legacy_pk=legacy_id,
                new_table="categories",
                new_pk=category.id,
            ))
            categories_imported += 1
        
        session.commit()
        report["results"]["categories"] = {"imported": categories_imported}
        print(f"  ✓ {categories_imported} categories imported")
        
        # 7. Import Invoices
        print("\n[7/7] Importing invoices...")
        invoices_imported = 0
        
        for row in legacy_conn.execute("SELECT * FROM core_invoice"):
            legacy_id = row["id"]
            existing = session.query(ImportMap).filter_by(
                legacy_table="core_invoice", legacy_pk=legacy_id
            ).first()
            if existing:
                continue
            
            business_id = legacy_to_new_business.get(row["business_id"])
            customer_id = legacy_to_new_customer.get(row["customer_id"])
            if not business_id or not customer_id:
                continue
            
            invoice = Invoice(
                business_id=business_id,
                customer_id=customer_id,
                invoice_number=row["invoice_number"],
                status=get_val(row, "status", "DRAFT"),
                description=get_val(row, "description", ""),
                total_amount=Decimal(str(get_val(row, "total_amount", 0))),
                net_total=Decimal(str(get_val(row, "net_total", 0))),
                tax_total=Decimal(str(get_val(row, "tax_total", 0))),
                legacy_id=legacy_id,
            )
            session.add(invoice)
            session.flush()
            
            session.add(ImportMap(
                legacy_table="core_invoice",
                legacy_pk=legacy_id,
                new_table="invoices",
                new_pk=invoice.id,
            ))
            invoices_imported += 1
        
        session.commit()
        report["results"]["invoices"] = {"imported": invoices_imported}
        print(f"  ✓ {invoices_imported} invoices imported")
    
    legacy_conn.close()
    
    report["total_imported"] = sum(r["imported"] for r in report["results"].values())
    
    print("\n=== IMPORT COMPLETE ===")
    print(f"Total records imported: {report['total_imported']}")
    
    return report


def verify(legacy_db: str, target_db_url: str) -> dict:
    """Verify import by comparing counts."""
    from app.models import User, Business, Customer, Supplier, Account, Category, Invoice
    from app.db import Base
    
    engine = create_engine(target_db_url)
    Session = sessionmaker(bind=engine)
    
    legacy_conn = get_legacy_connection(legacy_db)
    legacy_counts = count_legacy_tables(legacy_conn)
    legacy_conn.close()
    
    report = {
        "mode": "verify",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "comparisons": [],
        "status": "PASS",
    }
    
    with Session() as session:
        new_counts = {
            "auth_user": session.query(User).count(),
            "core_business": session.query(Business).count(),
            "core_customer": session.query(Customer).count(),
            "core_supplier": session.query(Supplier).count(),
            "core_account": session.query(Account).count(),
            "core_category": session.query(Category).count(),
            "core_invoice": session.query(Invoice).count(),
        }
    
    print("\n=== VERIFICATION REPORT ===")
    for table, legacy_count in legacy_counts.items():
        new_count = new_counts.get(table, 0)
        match = "✓" if new_count >= legacy_count else "✗"
        status = "PASS" if new_count >= legacy_count else "FAIL"
        if status == "FAIL":
            report["status"] = "FAIL"
        
        new_table = table.replace("auth_", "").replace("core_", "") + "s"
        if table == "auth_user":
            new_table = "users"
            
        print(f"  {match} {table} ({legacy_count}) → {new_table} ({new_count})")
        report["comparisons"].append({
            "legacy_table": table,
            "legacy_count": legacy_count,
            "new_table": new_table,
            "new_count": new_count,
            "status": status,
        })
    
    print(f"\nOverall: {report['status']}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Import legacy Django SQLite to FastAPI DB")
    parser.add_argument("--legacy-db", required=True, help="Path to legacy db.sqlite3")
    parser.add_argument("--target-db", default=None, help="Target DATABASE_URL (default from env)")
    parser.add_argument("--mode", choices=["dry-run", "import", "verify"], default="dry-run")
    parser.add_argument("--report-dir", default="reports", help="Directory for JSON reports")
    
    args = parser.parse_args()
    
    target_db = args.target_db or os.getenv("DATABASE_URL", "sqlite:///./cloverbooks.db")
    
    if args.mode == "dry-run":
        report = dry_run(args.legacy_db)
    elif args.mode == "import":
        report = import_data(args.legacy_db, target_db)
    elif args.mode == "verify":
        report = verify(args.legacy_db, target_db)
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)
    
    os.makedirs(args.report_dir, exist_ok=True)
    report_path = os.path.join(args.report_dir, f"legacy_import_{args.mode}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
