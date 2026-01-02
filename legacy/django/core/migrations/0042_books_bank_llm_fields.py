from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0041_bank_review_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankreviewrun",
            name="llm_explanations",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="bankreviewrun",
            name="llm_ranked_transactions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="bankreviewrun",
            name="llm_suggested_followups",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="booksreviewrun",
            name="llm_explanations",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="booksreviewrun",
            name="llm_ranked_issues",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="booksreviewrun",
            name="llm_suggested_checks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
