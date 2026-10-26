from django.urls import path

from . import mine, views

urlpatterns = [
    path("events/<int:event_id>/register", views.RegisterView.as_view()),
    path("me/registrations", views.MyRegistrations.as_view()),
    path("me/registrations/full", mine.MyRegistrationsFull.as_view()),
]
