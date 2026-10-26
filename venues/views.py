from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import CharField, ChoiceField, IntegerField, Serializer
from rest_framework.views import APIView

from accounts.permissions import IsApprover, IsCommitteeAccount, own_committee_id
from common.db import fetch_all, fetch_one
from events.guards import forbid_deciding_own_committee
from events.models import Event, EventSession

from .models import Venue, VenueBooking

VENUE_COLUMNS = (
    "SELECT v.venue_id, v.venue_name, v.capacity, v.location, v.status, "
    "       (SELECT COUNT(*) FROM venue_booking vb WHERE vb.venue_id = v.venue_id AND vb.flagged = 1) AS flagged "
    "FROM venue v "
)


class VenueBody(Serializer):
    venue_name = CharField(max_length=80)
    capacity = IntegerField(min_value=1)
    location = CharField(max_length=80, required=False, allow_blank=True, allow_null=True)
    status = ChoiceField(choices=[Venue.ACTIVE, Venue.SUSPENDED, Venue.REMOVED], required=False)


class VenueListCreate(APIView):
    """
    GET  /venues            public: active venues only.  ?all=1 (council/admin): every venue + status + flagged count
    POST /venues            council/admin add a venue
    """
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsApprover()]

    def get(self, request):
        if request.query_params.get("all") and request.user.is_authenticated and request.user.is_approver:
            return Response(fetch_all(VENUE_COLUMNS + "ORDER BY FIELD(v.status,'Active','Suspended','Removed'), v.venue_name"))
        return Response(fetch_all(
            "SELECT venue_id, venue_name, capacity, location FROM venue WHERE status = 'Active' ORDER BY venue_name"))

    def post(self, request):
        s = VenueBody(data=request.data)
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            v = Venue.objects.create(**s.validated_data)
        return Response(fetch_one(VENUE_COLUMNS + "WHERE v.venue_id = %s", [v.venue_id]), status=status.HTTP_201_CREATED)


class VenueDetail(APIView):
    """
    PATCH  /venues/{id}   council/admin edit, or set status Active / Suspended / Removed
    DELETE /venues/{id}   council/admin remove (soft: status = Removed, so booking history survives)
    Suspending or removing flags the venue's upcoming bookings for the council (DB trigger).
    """
    permission_classes = [IsApprover]

    def patch(self, request, venue_id):
        s = VenueBody(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        venue = Venue.objects.filter(pk=venue_id)
        if not venue.exists():
            raise NotFound()
        if s.validated_data:
            with transaction.atomic():
                venue.update(**s.validated_data)
        return Response(fetch_one(VENUE_COLUMNS + "WHERE v.venue_id = %s", [venue_id]))

    def delete(self, request, venue_id):
        with transaction.atomic():
            if not Venue.objects.filter(pk=venue_id).update(status=Venue.REMOVED):
                raise NotFound()
        return Response(fetch_one(VENUE_COLUMNS + "WHERE v.venue_id = %s", [venue_id]))


class VenueAvailability(APIView):
    """GET /venues/{id}/availability?date=YYYY-MM-DD: what is already booked that day."""
    permission_classes = [AllowAny]

    def get(self, request, venue_id):
        date = request.query_params.get("date")
        if not date:
            return Response({"error": "date=YYYY-MM-DD is required"}, status=400)
        venue = fetch_one("SELECT venue_id, venue_name, capacity FROM venue WHERE venue_id = %s", [venue_id])
        if not venue:
            raise NotFound()
        booked = fetch_all(
            "SELECT event, session_title, start_time, end_time, booking_status FROM event_schedule "
            "WHERE venue_name = %s AND session_date = %s AND booking_status IN ('Approved','Pending') "
            "ORDER BY start_time",
            [venue["venue_name"], date],
        )
        return Response({"venue": venue, "date": date, "bookings": booked})


class BookingBody(Serializer):
    venue_id = IntegerField()


class BookingCreate(APIView):
    """POST /events/{id}/sessions/{n}/bookings: ask for a venue (starts Pending). Venue must be Active (trigger)."""
    permission_classes = [IsCommitteeAccount]

    def post(self, request, event_id, session_no):
        s = BookingBody(data=request.data)
        s.is_valid(raise_exception=True)
        event = Event.objects.filter(pk=event_id).first()
        if not event or not EventSession.objects.filter(event_id=event_id, session_no=session_no).exists():
            raise NotFound()
        if event.committee_id != own_committee_id(request.user):
            raise PermissionDenied("This event belongs to another committee.")
        with transaction.atomic():
            VenueBooking.objects.create(event_id=event_id, session_no=session_no,
                                        venue_id=s.validated_data["venue_id"], status="Pending")
        return Response({"status": "Pending"}, status=status.HTTP_201_CREATED)


class BookingDecision(APIView):
    """Approve/reject a venue booking. Same approvers as events. Clash/unapproved-event rules are DB triggers."""
    permission_classes = [IsApprover]
    decision = None

    def post(self, request, event_id, session_no, venue_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            raise NotFound()
        forbid_deciding_own_committee(request.user, event.committee_id)
        with transaction.atomic():
            changed = VenueBooking.objects.filter(
                event_id=event_id, session_no=session_no, venue_id=venue_id, status="Pending"
            ).update(status=self.decision)
        if not changed:
            return Response({"error": "No pending booking found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": self.decision})


class FlaggedBookingDecision(APIView):
    """Council/admin settle a booking flagged because its venue was suspended/removed: keep it, or cancel it."""
    permission_classes = [IsApprover]
    keep = True

    def post(self, request, event_id, session_no, venue_id):
        event = Event.objects.filter(pk=event_id).first()
        if not event:
            raise NotFound()
        forbid_deciding_own_committee(request.user, event.committee_id)
        changes = {"flagged": False} if self.keep else {"flagged": False, "status": "Rejected"}
        with transaction.atomic():
            changed = VenueBooking.objects.filter(
                event_id=event_id, session_no=session_no, venue_id=venue_id, flagged=True
            ).update(**changes)
        if not changed:
            return Response({"error": "No flagged booking found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"kept": self.keep})
