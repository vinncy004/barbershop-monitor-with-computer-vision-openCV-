from django.contrib import admin
from .models import CCTVStream, ReportEvent, User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "phone")
    search_fields = ("username", "email", "phone")

@admin.register(CCTVStream)
class CCTVStreamAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "rtsp_url", "status", "active")
    search_fields = ("name", "rtsp_url", "user__email")

@admin.register(ReportEvent)
class ReportEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "timestamp", "duration_seconds")
    list_filter = ("event_type",)
    search_fields = ("user__email", "event_type")
