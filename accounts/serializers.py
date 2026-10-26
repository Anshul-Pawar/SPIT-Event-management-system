from django.conf import settings
from rest_framework import serializers

from .models import AppUser, Role


def check_domain(value: str) -> str:
    value = value.strip().lower()
    if not value.endswith("@" + settings.ALLOWED_EMAIL_DOMAIN):
        raise serializers.ValidationError(f"Use your @{settings.ALLOWED_EMAIL_DOMAIN} email.")
    return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        return check_domain(value)


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        value = check_domain(value)
        if AppUser.objects.filter(person__email=value).exists():
            raise serializers.ValidationError("This email already has an account. Log in instead.")
        if value == settings.ROOT_ADMIN_EMAIL.lower():
            raise serializers.ValidationError("This account is reserved.")
        return value


class AppUserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="person.name", read_only=True)
    email = serializers.CharField(source="person.email", read_only=True)
    committee_name = serializers.CharField(source="committee.name", read_only=True, default=None)
    is_root = serializers.BooleanField(read_only=True)

    class Meta:
        model = AppUser
        fields = ["id", "person", "name", "email", "role", "committee", "committee_name",
                  "is_permanent", "is_root", "is_active"]
        read_only_fields = fields


class AppUserUpdateSerializer(serializers.Serializer):
    """What a council member / admin may change on an account. Who may change what is in the view."""
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    committee = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)
    is_permanent = serializers.BooleanField(required=False)
