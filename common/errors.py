"""
Maps MySQL errors (mostly trigger SIGNALs) to HTTP statuses. Table comes from section 6.3 of the DB doc.
The triggers are the source of truth for business rules; we only translate their messages.
"""

# Trigger messages raised with SQLSTATE '45000' (MySQL error 1644).
TRIGGER_MESSAGES = {
    "Event is not approved yet": 409,
    "Registration deadline has passed": 409,
    "Event is full": 409,
    "Amount paid is more than the event fee": 422,
    "Venue capacity is less than event seats": 422,
    "Cannot approve booking for an unapproved event": 409,
    "Venue already booked for this time slot": 409,
    "Session date is before the registration deadline": 422,
    "Requested quantity is more than available stock": 422,
    "Set approved_by before approving the event": 422,
    "Venue is not available (suspended or removed)": 409,
    "A permanent admin can't be changed or removed": 403,
}

ER_SIGNAL_EXCEPTION = 1644      # trigger SIGNAL SQLSTATE '45000'
ER_DUP_ENTRY = 1062             # duplicate key (e.g. registering twice)
ER_NO_REFERENCED_ROW = 1452     # bad foreign key
ER_ROW_IS_REFERENCED = 1451     # delete blocked by a foreign key (e.g. a committee that still has events)
ER_CHECK_VIOLATED = 3819        # CHECK constraint (e.g. end_time > start_time)


def map_db_error(exc) -> tuple[int, str] | None:
    """Return (http_status, safe_message) for a known DB error, else None."""
    args = getattr(exc, "args", ())
    if len(args) < 2 or not isinstance(args[0], int):
        return None
    code, message = args[0], str(args[1])

    if code == ER_SIGNAL_EXCEPTION:
        for text, status in TRIGGER_MESSAGES.items():
            if text in message:
                return status, text
        return 409, message  # unknown trigger message: still a rule violation, not a crash
    if code == ER_DUP_ENTRY:
        return 409, "This record already exists"
    if code == ER_ROW_IS_REFERENCED:
        return 409, "This record is still in use, so it can't be deleted"
    if code == ER_NO_REFERENCED_ROW:
        return 422, "A referenced record does not exist"
    if code == ER_CHECK_VIOLATED:
        return 422, "A value breaks a database rule (check the dates, times and amounts)"
    return None
