from rest_framework.permissions import BasePermission

from committees.models import CommitteeMember


def roster_committee_ids(user) -> set[int]:
    """Committees this person is listed on (committee_member). Gives no rights; used to stop self-approval."""
    return set(CommitteeMember.objects.filter(student_id=user.person_id).values_list("committee_id", flat=True))


def own_committee_id(user) -> int | None:
    """The committee a committee account posts for, else None."""
    return user.committee_id if user.is_authenticated and user.is_committee_account else None


class IsApprover(BasePermission):
    """Student council or admin."""
    message = "Only the student council or an admin can do this."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_approver)


class IsStudent(BasePermission):
    """Student accounts (council members are students too). Committee and admin accounts can't register."""
    message = "Only students can do this."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.role in ("student", "council"))


class IsCommitteeAccount(BasePermission):
    message = "Only a committee account can do this."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_committee_account)
