"""Small rules that live in the app (they are NOT in the DB triggers)."""
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import roster_committee_ids


def forbid_deciding_own_committee(user, committee_id: int) -> None:
    """An approver listed on the organizing committee's roster can't decide its events (no self-approval)."""
    if committee_id in roster_committee_ids(user):
        raise PermissionDenied("You belong to the organizing committee, so someone else has to decide this.")
