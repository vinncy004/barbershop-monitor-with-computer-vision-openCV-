from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone
from datetime import date


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard_app", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product", models.CharField(max_length=200)),
                ("cost", models.FloatField(default=0.0)),
                ("created_at", models.DateField(default=date.today)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_items", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="BusinessPerformanceEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("month", models.CharField(max_length=7)),
                ("expenses", models.FloatField(default=0.0)),
                ("outcome", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="business_performance_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "month")}},
        ),
    ]
