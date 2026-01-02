import os
import django
from decimal import Decimal
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "minibooks_project.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from core.models import Business, BankAccount, BankTransaction, TaxRate, Account
from core.views import api_banking_feed_add_entry

def reproduce():
    # Setup
    user, _ = User.objects.get_or_create(username="testuser", defaults={"email": "test@example.com"})
    if not user.check_password("password"):
        user.set_password("password")
        user.save()
    
    business = Business.objects.filter(owner_user=user).first()
    if not business:
        business = Business.objects.create(name="Test Biz", owner_user=user, currency="USD")
    
    # Ensure default accounts
    from core.accounting_defaults import ensure_default_accounts
    ensure_default_accounts(business)
    
    # Bank Account
    ledger_bank, _ = Account.objects.get_or_create(
        business=business, 
        code="1000", 
        defaults={"name": "Bank", "type": "ASSET"}
    )
    bank_account, _ = BankAccount.objects.get_or_create(
        business=business, 
        account=ledger_bank,
        defaults={"name": "Test Bank"}
    )
    
    # Transaction
    tx, _ = BankTransaction.objects.get_or_create(
        bank_account=bank_account,
        external_id="test-1",
        defaults={
            "date": "2025-11-27",
            "amount": Decimal("-15.50"),
            "description": "Stripe processing fees",
            "status": "NEW"
        }
    )
    
    # Tax Rate
    tax_rate, _ = TaxRate.objects.get_or_create(
        business=business,
        code="GST",
        defaults={
            "name": "GST/HST",
            "percentage": Decimal("13.00"),
            "is_recoverable": True
        }
    )
    
    # Reset status if needed
    tx.status = "NEW"
    tx.save()
    
    # Request
    factory = RequestFactory()
    payload = {
        "account_id": Account.objects.get(business=business, code="5010").id, # Operating Expenses
        "direction": "OUT",
        "amount": "15,50",
        "tax_treatment": "INCLUDED",
        "memo": "Stripe processing fees",
        "tax_rate_id": tax_rate.id
    }
    
    request = factory.post(
        f"/api/banking/feed/transactions/{tx.id}/add/",
        data=json.dumps(payload),
        content_type="application/json"
    )
    request.user = user
    
    # Execute
    response = api_banking_feed_add_entry(request, tx.id)
    
    print(f"Status Code: {response.status_code}")
    print(f"Content: {response.content.decode()}")

if __name__ == "__main__":
    try:
        reproduce()
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
