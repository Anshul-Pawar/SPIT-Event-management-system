from django.urls import path

from . import views

urlpatterns = [
    path("admin/alerts", views.Alerts.as_view()),
    path("admin/alerts/<int:alert_id>/resolve", views.ResolveAlert.as_view()),
    path("admin/activity", views.Activity.as_view()),
    path("admin/fill-rate", views.FillRate.as_view()),
    path("admin/trend", views.Trend.as_view()),
    path("admin/health", views.Health.as_view()),
    path("admin/finance", views.Finance.as_view()),
    path("admin/stats", views.Stats.as_view()),
]
