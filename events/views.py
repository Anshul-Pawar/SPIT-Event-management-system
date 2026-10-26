from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsApprover, IsCommitteeAccount, own_committee_id
from common.db import fetch_all, fetch_one

from .guards import forbid_deciding_own_committee
from .models import Event, EventSession
from .serializers import DecisionSerializer, EventCreateSerializer


class EventListCreate(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsCommitteeAccount()]

    def get(self, request):
        """Public listing: approved events still open for registration."""
        return Response(fetch_all("SELECT * FROM v_public_events"))

    def post(self, request):
        """A committee account proposes an event (for its own committee) with its sessions. Starts Pending."""
        s = EventCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        with transaction.atomic():
            event = Event.objects.create(
                title=d["title"], fee=d["fee"], max_seats=d["max_seats"], reg_deadline=d["reg_deadline"],
                committee_id=own_committee_id(request.user), category_id=d["cat_id"],
            )
            for n, sess in enumerate(d["sessions"], start=1):
                EventSession.objects.create(event_id=event.event_id, session_no=n, **sess)
        return Response({"event_id": event.event_id, "approval_status": Event.PENDING},
                        status=status.HTTP_201_CREATED)


class EventDetail(APIView):
    permission_classes = [AllowAny]

    def get(self, request, event_id):
        event = fetch_one("SELECT * FROM event_overview WHERE event_id = %s", [event_id])
        if not event:
            raise NotFound()
        # Unapproved events are visible only to approvers and to the organizing committee's account.
        if event["approval_status"] != Event.APPROVED:
            u = request.user
            ok = u.is_authenticated and (
                u.is_approver
                or Event.objects.filter(pk=event_id, committee_id=own_committee_id(u)).exists()
            )
            if not ok:
                raise NotFound()
        # event_schedule has no event_id column, so read sessions + bookings directly.
        sessions = fetch_all(
            "SELECT s.session_no, s.title, s.session_date, s.start_time, s.end_time, "
            "       v.venue_id, v.venue_name, vb.status AS booking_status "
            "FROM event_session s "
            "LEFT JOIN venue_booking vb ON vb.event_id = s.event_id AND vb.session_no = s.session_no "
            "LEFT JOIN venue v ON v.venue_id = vb.venue_id "
            "WHERE s.event_id = %s ORDER BY s.session_no",
            [event_id],
        )
        return Response({**event, "sessions": sessions})


class PendingApprovals(APIView):
    """What an approver needs to act on. (Needs ids for the approve / reject buttons, so this reads the tables directly.)"""
    permission_classes = [IsApprover]

    def get(self, request):
        events = fetch_all(
            "SELECT e.event_id, e.title, c.name AS committee, e.fee, e.max_seats, e.reg_deadline "
            "FROM event e JOIN committee c ON c.committee_id = e.committee_id "
            "WHERE e.approval_status = 'Pending' ORDER BY e.event_id"
        )
        bookings = fetch_all(
            "SELECT vb.event_id, vb.session_no, vb.venue_id, e.title AS event, v.venue_name, "
            "       s.session_date, s.start_time, s.end_time "
            "FROM venue_booking vb "
            "JOIN event e ON e.event_id = vb.event_id "
            "JOIN event_session s ON s.event_id = vb.event_id AND s.session_no = vb.session_no "
            "JOIN venue v ON v.venue_id = vb.venue_id "
            "WHERE vb.status = 'Pending' ORDER BY s.session_date"
        )
        flagged = fetch_all(
            "SELECT vb.event_id, vb.session_no, vb.venue_id, e.title AS event, v.venue_name, v.status AS venue_status, "
            "       vb.status AS booking_status, s.session_date, s.start_time, s.end_time "
            "FROM venue_booking vb "
            "JOIN event e ON e.event_id = vb.event_id "
            "JOIN event_session s ON s.event_id = vb.event_id AND s.session_no = vb.session_no "
            "JOIN venue v ON v.venue_id = vb.venue_id "
            "WHERE vb.flagged = 1 ORDER BY s.session_date"
        )
        return Response({"events": events, "venue_bookings": bookings, "flagged_bookings": flagged})


class EventDecision(APIView):
    """POST /events/{id}/approve or /reject. Council or admin decides."""
    permission_classes = [IsApprover]
    decision = None  # "Approved" or "Rejected"

    def post(self, request, event_id):
        s = DecisionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        event = get_object_or_404(Event, pk=event_id)
        forbid_deciding_own_committee(request.user, event.committee_id)
        with transaction.atomic():
            # Only a Pending event can be decided; the WHERE makes it safe if two approvers click together.
            changed = Event.objects.filter(pk=event_id, approval_status=Event.PENDING).update(
                approved_by=request.user.person,
                approval_status=self.decision,
                approval_remarks=s.validated_data["remarks"] or None,
            )
        if not changed:
            return Response({"error": "This event has already been decided"}, status=status.HTTP_409_CONFLICT)
        return Response({"event_id": event_id, "approval_status": self.decision})
