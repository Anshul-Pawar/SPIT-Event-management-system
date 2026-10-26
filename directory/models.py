"""
Unmanaged models over tables created by sql/01_schema.sql. Django never creates, alters or drops them.
"""
from django.db import models


class Person(models.Model):
    person_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=80)
    email = models.CharField(max_length=100, unique=True)

    class Meta:
        managed = False
        db_table = "person"


class Student(models.Model):
    person = models.OneToOneField(Person, primary_key=True, on_delete=models.DO_NOTHING,
                                  db_column="person_id", related_name="student")
    roll_no = models.CharField(max_length=64, unique=True)

    class Meta:
        managed = False
        db_table = "student"
