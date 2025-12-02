# Add unique constraint to email_token after fixing duplicates

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_fix_duplicate_email_tokens'),
    ]

    operations = [
        # Now add the unique constraint
        migrations.AlterField(
            model_name='invoice',
            name='email_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
