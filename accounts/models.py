from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Role(models.TextChoices):
    STUDENT = "student", "Student"
    COMMITTEE = "committee", "Committee"
    COUNCIL = "council", "Student council"
    ADMIN = "admin", "Admin"


# Roles that approve events / venue bookings and see every dashboard.
APPROVER_ROLES = {Role.COUNCIL, Role.ADMIN}
# Highest role each manager may hand out. Only admins can make admins.
GRANTABLE_ROLES = {
    Role.ADMIN: {Role.STUDENT, Role.COMMITTEE, Role.COUNCIL, Role.ADMIN},
    Role.COUNCIL: {Role.STUDENT, Role.COMMITTEE, Role.COUNCIL},
}


class AppUserManager(BaseUserManager):
    def create_user(self, person, password, role=Role.STUDENT, **extra):
        user = self.model(person=person, role=role, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user


class AppUser(AbstractBaseUser):
    """
    Login account for a person in the `person` table. Lives in its own table, so the
    22 designed tables stay untouched.

    Four roles: student (registers), committee (a committee's own account: posts events and
    requests venues for `committee`), council and admin (approve, manage venues and accounts,
    see every dashboard). Every new account starts as student.

    Permanent admins can never be demoted, deactivated or deleted; a trigger on app_user
    enforces that in the DB too. Only the root admin (settings.ROOT_ADMIN_EMAIL) can make one.
    """
    person = models.OneToOneField("directory.Person", on_delete=models.PROTECT,
                                  db_column="person_id", related_name="app_user")
    password = models.CharField(max_length=128, db_column="password_hash")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    committee = models.ForeignKey("committees.Committee", null=True, blank=True, on_delete=models.PROTECT,
                                  db_column="committee_id", related_name="+")
    is_permanent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AppUserManager()

    USERNAME_FIELD = "person"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "app_user"
        constraints = [
            # A committee account belongs to exactly one committee; nobody else has one.
            models.CheckConstraint(
                condition=(models.Q(role="committee", committee__isnull=False)
                           | (~models.Q(role="committee") & models.Q(committee__isnull=True))),
                name="app_user_committee_iff_role"),
            models.CheckConstraint(
                condition=models.Q(is_permanent=False) | models.Q(role="admin", is_active=True),
                name="app_user_permanent_is_admin"),
        ]

    def get_username(self):
        return self.person.email

    @property
    def is_root(self) -> bool:
        return self.is_permanent and self.person.email.lower() == settings.ROOT_ADMIN_EMAIL.lower()

    @property
    def is_approver(self) -> bool:
        return self.is_active and self.role in APPROVER_ROLES

    @property
    def is_admin_role(self) -> bool:
        return self.is_active and self.role == Role.ADMIN

    @property
    def is_committee_account(self) -> bool:
        return self.is_active and self.role == Role.COMMITTEE and self.committee_id is not None
