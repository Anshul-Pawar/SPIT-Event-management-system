from django.db import models


class Venue(models.Model):
    ACTIVE, SUSPENDED, REMOVED = "Active", "Suspended", "Removed"

    venue_id = models.AutoField(primary_key=True)
    venue_name = models.CharField(max_length=80, unique=True)
    capacity = models.IntegerField()
    location = models.CharField(max_length=80, null=True)
    # Suspending / removing a venue flags its upcoming bookings (trigger trg_venue_status_flag).
    status = models.CharField(max_length=9, db_default=ACTIVE)

    class Meta:
        managed = False
        db_table = "venue"


class VenueBooking(models.Model):
    """
    FK is (event_id, session_no) -> event_session, which is a composite key. Django 5.2 can't
    declare a ForeignKey to a composite PK, so these two are plain integer fields.
    """
    pk = models.CompositePrimaryKey("event_id", "session_no", "venue_id")
    event_id = models.IntegerField()
    session_no = models.SmallIntegerField()
    venue = models.ForeignKey(Venue, on_delete=models.DO_NOTHING, db_column="venue_id")
    status = models.CharField(max_length=8, db_default="Pending")
    # Set by the DB when the venue is suspended/removed; council then keeps or cancels the booking.
    flagged = models.BooleanField(db_default=False)

    class Meta:
        managed = False
        db_table = "venue_booking"
