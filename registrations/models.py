from django.db import models
from django.db.models.functions import Now


class Registration(models.Model):
    pk = models.CompositePrimaryKey("event_id", "student_id")
    event = models.ForeignKey("events.Event", on_delete=models.DO_NOTHING, db_column="event_id")
    student = models.ForeignKey("directory.Student", on_delete=models.DO_NOTHING, db_column="student_id")
    reg_date = models.DateTimeField(db_default=Now())
    status = models.CharField(max_length=10, db_default="Registered")
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2, db_default=0)

    class Meta:
        managed = False
        db_table = "registration"
