from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import CharField, EmailField, IntegerField, Serializer
from rest_framework.views import APIView

from accounts.models import AppUser
from accounts.permissions import IsApprover
from common.db import fetch_all, fetch_one
from events.models import Event

from .models import Committee, CommitteeMember

# What a committee account may change on its own committee. Council / admin may change everything.
SELF_EDITABLE = {"coordinator_name", "coordinator_email"}


class CommitteeBody(Serializer):
    name = CharField(max_length=80)
    email = EmailField(max_length=100)
    founded_year = IntegerField(min_value=1901, max_value=2155, required=False, allow_null=True)
    coordinator_name = CharField(max_length=80, required=False, allow_null=True, allow_blank=True)
    coordinator_email = EmailField(max_length=100, required=False, allow_null=True, allow_blank=True)

    def validate(self, data):
        # Blank coordinator fields mean "not set".
        return {k: (None if v == "" else v) for k, v in data.items()}


class CommitteeList(APIView):
    """GET public list  |  POST council / admin add a committee"""
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsApprover()]

    def get(self, request):
        return Response(fetch_all("SELECT * FROM committee_summary ORDER BY committee"))

    def post(self, request):
        s = CommitteeBody(data=request.data)
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            c = Committee.objects.create(**s.validated_data)
        return Response(fetch_one("SELECT * FROM committee_summary WHERE committee_id = %s", [c.committee_id]),
                        status=status.HTTP_201_CREATED)


class CommitteeDetail(APIView):
    """
    GET    public detail with member list
    PATCH  council / admin edit anything; the committee's own account edits only the coordinator details
    DELETE council / admin, only while the committee has no events and no login account
    """
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def patch(self, request, committee_id):
        s = CommitteeBody(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        u, d = request.user, s.validated_data
        own = u.is_committee_account and u.committee_id == committee_id
        if not (u.is_approver or own):
            raise PermissionDenied("Only the council, an admin or this committee's account can edit it.")
        if not u.is_approver and set(d) - SELF_EDITABLE:
            raise PermissionDenied("A committee account can only change its coordinator details.")
        committee = Committee.objects.filter(pk=committee_id)
        if not committee.exists():
            raise NotFound()
        if d:
            with transaction.atomic():
                committee.update(**d)
        return Response(fetch_one("SELECT * FROM committee_summary WHERE committee_id = %s", [committee_id]))

    def delete(self, request, committee_id):
        if not request.user.is_approver:
            raise PermissionDenied("Only the council or an admin can delete a committee.")
        if not Committee.objects.filter(pk=committee_id).exists():
            raise NotFound()
        if Event.objects.filter(committee_id=committee_id).exists():
            return Response({"error": "This committee has events, so it can't be deleted."}, status=status.HTTP_409_CONFLICT)
        if AppUser.objects.filter(committee_id=committee_id).exists():
            return Response({"error": "A login account is linked to this committee. Change its role first."},
                            status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            Committee.objects.filter(pk=committee_id).delete()   # roster rows cascade in the DB
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get(self, request, committee_id):
        row = fetch_one("SELECT * FROM committee_summary WHERE committee_id = %s", [committee_id])
        if not row:
            raise NotFound()
        members = fetch_all(
            "SELECT p.name, s.roll_no, cm.role, cm.joined_on FROM committee_member cm "
            "JOIN student s ON s.person_id = cm.student_id JOIN person p ON p.person_id = s.person_id "
            "WHERE cm.committee_id = %s ORDER BY cm.joined_on, p.name",
            [committee_id],
        )
        return Response({**row, "member_list": members})


class MemberBody(Serializer):
    student_id = IntegerField()
    role = CharField(max_length=40, default="Member")


class CommitteeMemberAdd(APIView):
    """The committee's own account, council or admin adds a student to the roster (a roster grants no rights)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, committee_id):
        s = MemberBody(data=request.data)
        s.is_valid(raise_exception=True)
        u = request.user
        if not (u.is_approver or (u.is_committee_account and u.committee_id == committee_id)):
            raise PermissionDenied("Only this committee's account, the council or an admin can add members.")
        with transaction.atomic():
            CommitteeMember.objects.create(committee_id=committee_id, student_id=s.validated_data["student_id"],
                                           role=s.validated_data["role"])
        return Response(status=status.HTTP_201_CREATED)
