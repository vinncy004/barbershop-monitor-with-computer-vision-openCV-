from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .validators import validate_stream_url


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    rtsp_url = models.CharField(
        max_length=500, blank=True, null=True, validators=[validate_stream_url]
    )

    def __str__(self):
        return self.email or self.username

class CCTVStream(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streams")
    name = models.CharField(max_length=100)
    rtsp_url = models.CharField(max_length=500, validators=[validate_stream_url])
    active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=50, default="unknown")

    def __str__(self):
        return f"{self.name} ({self.user.email})"

class ReportEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="events")
    timestamp = models.DateTimeField()
    event_type = models.CharField(max_length=100)
    duration_seconds = models.FloatField(default=0.0)
    details = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.event_type} @ {self.timestamp}"


class InventoryItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inventory_items")
    product = models.CharField(max_length=200)
    cost = models.FloatField(default=0.0)
    created_at = models.DateField(default=date.today)

    def __str__(self):
        return f"{self.product} - {self.cost}"


class BusinessPerformanceEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="business_performance_entries")
    month = models.CharField(max_length=7)
    expenses = models.FloatField(default=0.0)
    outcome = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "month")

    def __str__(self):
        return f"{self.month} - {self.expenses}"