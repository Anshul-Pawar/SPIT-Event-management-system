from django.db import models


class Committee(models.Model):
    committee_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=80, unique=True)
    email = models.CharField(max_length=100, unique=True)
    founded_year = models.IntegerField(null=True)
    # Faculty coordinator as plain contact details (there is no faculty table).
    coordinator_name = models.CharField(max_length=80, null=True)
    coordinator_email = models.CharField(max_length=100, null=True)

    class Meta:
        managed = False
        db_table = "committee"


class CommitteeMember(models.Model):
    pk = models.CompositePrimaryKey("committee_id", "student_id")
    committee = models.ForeignKey(Committee, on_delete=models.DO_NOTHING, db_column="committee_id")
    student = models.ForeignKey("directory.Student", on_delete=models.DO_NOTHING, db_column="student_id")
    role = models.CharField(max_length=40, default="Member")
    joined_on = models.DateField(null=True)

    class Meta:
        managed = False
        db_table = "committee_member"
