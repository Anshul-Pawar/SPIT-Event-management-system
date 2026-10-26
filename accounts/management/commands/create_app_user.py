"""
Bootstrap the root admin:   python manage.py create_app_user --email anshul.pawar25@spit.ac.in
The root email (settings.ROOT_ADMIN_EMAIL) always becomes a permanent admin. Any other email becomes
a student, same as signing up; promote it from the dashboard.
"""
from getpass import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import AppUser, Role
from directory.models import Person


class Command(BaseCommand):
    help = "Create a login account (creating the person row if needed). The root email becomes the permanent admin."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", help="Name for a new person row (default: part before the @).")
        parser.add_argument("--password", help="If omitted you'll be prompted.")

    def handle(self, *args, **opts):
        email = opts["email"].strip().lower()
        if not email.endswith("@" + settings.ALLOWED_EMAIL_DOMAIN):
            raise CommandError(f"Email must end with @{settings.ALLOWED_EMAIL_DOMAIN}.")
        if AppUser.objects.filter(person__email__iexact=email).exists():
            raise CommandError("That person already has an account.")
        password = opts["password"] or getpass("Password: ")
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")
        root = email == settings.ROOT_ADMIN_EMAIL.lower()
        with transaction.atomic():
            person = Person.objects.filter(email__iexact=email).first() \
                or Person.objects.create(name=opts["name"] or email.split("@")[0], email=email)
            AppUser.objects.create_user(person=person, password=password,
                                        role=Role.ADMIN if root else Role.STUDENT, is_permanent=root)
        self.stdout.write(self.style.SUCCESS(
            f"Created {'PERMANENT ADMIN' if root else 'student'} account for {person.name}"))
