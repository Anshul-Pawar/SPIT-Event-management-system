"""
UI helper: everything a committee account needs to see about its committee's events
(including Pending / Rejected ones, which the public listing hides).
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCommitteeAccount, own_committee_id
from common.db import fetch_all


class MyCommitteeEvents(APIView):
    """GET /api/me/events: my committee's events, with sessions and venue bookings."""
    permission_classes = [IsCommitteeAccount]

    def get(self, request):
        ids = [own_committee_id(request.user)]
        marks = ",".join(["%s"] * len(ids))
        events = fetch_all(
            "SELECT e.event_id, e.title, e.committee_id, c.name AS committee, cat.cat_name AS category, "
            "       e.fee, e.max_seats, e.reg_deadline, e.approval_status, e.approval_remarks, "
            "       (SELECT COUNT(*) FROM registration r "
            "         WHERE r.event_id = e.event_id AND r.status <> 'Cancelled') AS seats_taken "
            "FROM event e "
            "JOIN committee c ON c.committee_id = e.committee_id "
            "JOIN category cat ON cat.cat_id = e.cat_id "
            f"WHERE e.committee_id IN ({marks}) "
            "ORDER BY e.event_id DESC",
            ids,
        )
        if not events:
            return Response([])

        event_ids = [e["event_id"] for e in events]
        emarks = ",".join(["%s"] * len(event_ids))
        rows = fetch_all(
            "SELECT s.event_id, s.session_no, s.title, s.session_date, s.start_time, s.end_time, "
            "       vb.venue_id, v.venue_name, vb.status AS booking_status "
            "FROM event_session s "
            "LEFT JOIN venue_booking vb ON vb.event_id = s.event_id AND vb.session_no = s.session_no "
            "LEFT JOIN venue v ON v.venue_id = vb.venue_id "
            f"WHERE s.event_id IN ({emarks}) "
            "ORDER BY s.event_id, s.session_no, v.venue_name",
            event_ids,
        )

        # One session can have several venue requests, so fold the joined rows back into sessions.
        by_event: dict[int, dict[int, dict]] = {}
        for r in rows:
            sessions = by_event.setdefault(r["event_id"], {})
            s = sessions.setdefault(r["session_no"], {
                "session_no": r["session_no"], "title": r["title"], "session_date": r["session_date"],
                "start_time": r["start_time"], "end_time": r["end_time"], "bookings": [],
            })
            if r["venue_id"] is not None:
                s["bookings"].append({"venue_id": r["venue_id"], "venue_name": r["venue_name"],
                                      "status": r["booking_status"]})
        for e in events:
            e["sessions"] = list(by_event.get(e["event_id"], {}).values())
        return Response(events)
