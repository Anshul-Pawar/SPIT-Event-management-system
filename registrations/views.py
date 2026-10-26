from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from common.db import fetch_all
from directory.models import Student
from events.models import Event

from .models import Registration
from .payments import get_gateway


class RegisterView(APIView):
    """POST /events/{id}/register   |   DELETE /events/{id}/register (cancel)"""
    permission_classes = [IsStudent]

    def post(self, request, event_id):
        with transaction.atomic():
            # Lock the event row so two students can't both take the last seat. The triggers
            # enforce approved / deadline / seats / amount; we just surface their errors.
            event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)
            # Accounts made by signup have no student row yet: make one (roll no = part before the @).
            Student.objects.get_or_create(person_id=request.user.person_id,
                                          defaults={"roll_no": request.user.person.email.split("@")[0]})
            result = get_gateway().charge(student_id=request.user.person_id, event_id=event_id, amount=event.fee)
            Registration.objects.create(event_id=event_id, student_id=request.user.person_id,
                                        amount_paid=result.amount_paid)
        return Response({"event_id": event_id, "status": "Registered"}, status=status.HTTP_201_CREATED)

    def delete(self, request, event_id):
        with transaction.atomic():
            changed = Registration.objects.filter(
                event_id=event_id, student_id=request.user.person_id, status="Registered"
            ).update(status="Cancelled")
        if not changed:
            return Response({"error": "No active registration found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"event_id": event_id, "status": "Cancelled"})


class MyRegistrations(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        student = Student.objects.filter(pk=request.user.person_id).first()
        if not student:
            return Response([])
        return Response(fetch_all("SELECT * FROM student_registrations WHERE roll_no = %s", [student.roll_no]))
