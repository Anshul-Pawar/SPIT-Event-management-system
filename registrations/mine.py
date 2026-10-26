"""
UI helper: the student's registrations WITH event_id.
(The existing /me/registrations reads the student_registrations view, which only has the event title,
 and titles are not unique, so the UI can't link or match on it.)
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from common.db import fetch_all


class MyRegistrationsFull(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return Response(fetch_all(
            "SELECT r.event_id, e.title, c.name AS committee, e.fee, "
            "       (SELECT MIN(s.session_date) FROM event_session s WHERE s.event_id = e.event_id) AS event_date, "
            "       r.reg_date, r.status, r.amount_paid "
            "FROM registration r "
            "JOIN event e ON e.event_id = r.event_id "
            "JOIN committee c ON c.committee_id = e.committee_id "
            "WHERE r.student_id = %s "
            "ORDER BY r.reg_date DESC",
            [request.user.person_id],
        ))
