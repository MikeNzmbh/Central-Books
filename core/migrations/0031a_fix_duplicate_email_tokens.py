# Data migration to fix duplicate email_token values

import uuid
from django.db import migrations


def fix_duplicate_email_tokens(apps, schema_editor):
    """Regenerate unique email_token for all invoices."""
    Invoice = apps.get_model('core', 'Invoice')
    
    # Update all invoices with new unique UUIDs
    for invoice in Invoice.objects.all():
        invoice.email_token = uuid.uuid4()
        invoice.save(update_fields=['email_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_invoice_email_fields_no_unique'),
    ]

    operations = [
        migrations.RunPython(fix_duplicate_email_tokens, migrations.RunPython.noop),
    ]
