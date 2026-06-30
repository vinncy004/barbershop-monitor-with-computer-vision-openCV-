from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    rtsp_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.email or self.username

class CCTVStream(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streams")
    name = models.CharField(max_length=100)
    rtsp_url = models.URLField()
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