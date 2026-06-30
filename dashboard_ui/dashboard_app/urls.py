from django.urls import path
from . import views

app_name = "dashboard_app"

urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/daily/", views.daily_report, name="daily_report"),
    path("dashboard/weekly/", views.weekly_report, name="weekly_report"),
    path("dashboard/monthly/", views.monthly_report, name="monthly_report"),
    path("dashboard/clear-history/", views.clear_history, name="clear_history"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("profile/add-stream/", views.add_stream, name="add_stream"),
    path("profile/remove-stream/<int:stream_id>/", views.remove_stream, name="remove_stream"),
]
