from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("api/", include("accounts.urls")),
    path("api/", include("committees.urls")),
    path("api/", include("events.urls")),
    path("api/", include("venues.urls")),
    path("api/", include("registrations.urls")),
    path("api/", include("monitoring.urls")),
    # The UI: plain HTML/CSS/JS in /web, served by Django itself (same origin as the API, so no CORS).
    path("", serve, {"path": "index.html", "document_root": settings.WEB_DIR}),
    re_path(r"^(?P<path>.+)$", serve, {"document_root": settings.WEB_DIR}),
]
