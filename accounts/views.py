from django.db import transaction
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from committees.models import Committee
from directory.models import Person

from .models import GRANTABLE_ROLES, AppUser, Role
from .permissions import IsApprover
from .serializers import AppUserSerializer, AppUserUpdateSerializer, LoginSerializer, SignupSerializer


def _login_response(user, code=status.HTTP_200_OK):
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": AppUserSerializer(user).data}, status=code)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        # Same error for unknown email and wrong password, so emails can't be probed.
        bad = Response({"error": "Wrong email or password"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            user = AppUser.objects.select_related("person").get(person__email__iexact=s.validated_data["email"])
        except AppUser.DoesNotExist:
            return bad
        if not user.is_active or not user.check_password(s.validated_data["password"]):
            return bad
        return _login_response(user)


class SignupView(APIView):
    """
    POST /auth/signup {email, password}. Every new account is a student; council/admin promote later.
    People already in the directory keep their row; new people get a person row named after the
    part before the @. The student row is made on their first registration (see registrations.views).
    """
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        s = SignupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"]
        with transaction.atomic():
            person = Person.objects.filter(email__iexact=email).first()
            if person is None:
                person = Person.objects.create(name=email.split("@")[0], email=email)
            user = AppUser.objects.create_user(person=person, password=s.validated_data["password"])
        return _login_response(user, status.HTTP_201_CREATED)


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        u = request.user
        committees = [{"committee_id": u.committee_id, "name": u.committee.name}] if u.is_committee_account else []
        return Response({
            **AppUserSerializer(u).data,
            "is_approver": u.is_approver,
            "committees": committees,
        })


class UserList(generics.ListAPIView):
    """Council / admin: every account. Accounts are created by signing up, never here."""
    permission_classes = [IsApprover]
    queryset = AppUser.objects.select_related("person", "committee").order_by("id")
    serializer_class = AppUserSerializer


class UserDetail(APIView):
    """
    PATCH /admin/users/{id} {role?, committee?, is_active?, is_permanent?}
      - council can set student / committee / council, and can't touch admins
      - admin can set any role, on anyone who isn't permanent
      - permanent admins can't be changed by anyone; only the root admin can make one
    """
    permission_classes = [IsApprover]

    def get(self, request, pk):
        return Response(AppUserSerializer(self._target(pk)).data)

    def patch(self, request, pk):
        s = AppUserUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        actor, target = request.user, self._target(pk)

        if target.is_permanent:
            raise PermissionDenied("A permanent admin can't be changed by anyone.")
        if target.role == Role.ADMIN and actor.role != Role.ADMIN:
            raise PermissionDenied("Only an admin can change an admin's account.")

        if d.get("is_permanent"):
            if not actor.is_root:
                raise PermissionDenied("Only the root admin can make someone a permanent admin.")
            d["role"] = Role.ADMIN
            if d.get("is_active") is False:
                raise ValidationError({"is_active": "A permanent admin must stay active."})
            target.is_active = True
            target.is_permanent = True

        role = d.get("role", target.role)
        if role != target.role and role not in GRANTABLE_ROLES.get(actor.role, set()):
            raise PermissionDenied(f"You can't make someone {role}.")
        if role == Role.COMMITTEE:
            cid = d.get("committee", target.committee_id)
            if cid is None:
                raise ValidationError({"committee": "Pick the committee this account posts for."})
            if not Committee.objects.filter(pk=cid).exists():
                raise ValidationError({"committee": "No such committee."})
            target.committee_id = cid
        else:
            target.committee_id = None
        target.role = role
        if "is_active" in d and not target.is_permanent:
            target.is_active = d["is_active"]

        with transaction.atomic():
            target.save()
        if not target.is_active:
            Token.objects.filter(user=target).delete()
        return Response(AppUserSerializer(target).data)

    @staticmethod
    def _target(pk):
        target = AppUser.objects.select_related("person", "committee").filter(pk=pk).first()
        if not target:
            raise NotFound()
        return target
