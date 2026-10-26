from django.urls import path

from . import views

urlpatterns = [
    path("venues", views.VenueListCreate.as_view()),
    path("venues/<int:venue_id>", views.VenueDetail.as_view()),
    path("venues/<int:venue_id>/availability", views.VenueAvailability.as_view()),
    path("events/<int:event_id>/sessions/<int:session_no>/bookings", views.BookingCreate.as_view()),
    path("events/<int:event_id>/sessions/<int:session_no>/bookings/<int:venue_id>/approve",
         views.BookingDecision.as_view(decision="Approved")),
    path("events/<int:event_id>/sessions/<int:session_no>/bookings/<int:venue_id>/reject",
         views.BookingDecision.as_view(decision="Rejected")),
    # Flagged bookings (venue suspended/removed after booking): keep it, or cancel it.
    path("events/<int:event_id>/sessions/<int:session_no>/bookings/<int:venue_id>/keep",
         views.FlaggedBookingDecision.as_view(keep=True)),
    path("events/<int:event_id>/sessions/<int:session_no>/bookings/<int:venue_id>/cancel",
         views.FlaggedBookingDecision.as_view(keep=False)),
]
