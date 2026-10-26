from django.db import models
from django.db.models.functions import Now


class Category(models.Model):
    cat_id = models.AutoField(primary_key=True)
    cat_name = models.CharField(max_length=40, unique=True)

    class Meta:
        managed = False
        db_table = "category"


class Event(models.Model):
    PENDING, APPROVED, REJECTED = "Pending", "Approved", "Rejected"
    STATUS_CHOICES = [(PENDING, PENDING), (APPROVED, APPROVED), (REJECTED, REJECTED)]

    event_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=120)
    fee = models.DecimalField(max_digits=8, decimal_places=2, db_default=0)
    max_seats = models.IntegerField()
    reg_deadline = models.DateField()
    committee = models.ForeignKey("committees.Committee", on_delete=models.DO_NOTHING, db_column="committee_id")
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING, db_column="cat_id")
    # Points at person: the council member or admin who decided.
    approved_by = models.ForeignKey("directory.Person", null=True, on_delete=models.DO_NOTHING,
                                    db_column="approved_by", related_name="+")
    approval_status = models.CharField(max_length=8, choices=STATUS_CHOICES, db_default=PENDING)
    approval_remarks = models.CharField(max_length=200, null=True)

    class Meta:
        managed = False
        db_table = "event"


class EventSession(models.Model):
    pk = models.CompositePrimaryKey("event_id", "session_no")
    event = models.ForeignKey(Event, on_delete=models.DO_NOTHING, db_column="event_id", related_name="sessions")
    session_no = models.SmallIntegerField()
    title = models.CharField(max_length=100)
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        managed = False
        db_table = "event_session"
