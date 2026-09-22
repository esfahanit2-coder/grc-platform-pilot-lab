from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.audit.services import record_audit_event
from apps.identity.models import MFADevice
from apps.identity.authentication import enforce_csrf
from apps.identity.mfa_security import verify_mfa_device_once
from apps.identity.services import create_pending_mfa_device, tenant_requires_mfa

User = get_user_model()
CHALLENGE_SALT = "grc.mfa.challenge.v1"
CHALLENGE_MAX_AGE = 300


def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _challenge(user, purpose):
    return signing.dumps({"user_id": user.pk, "purpose": purpose}, salt=CHALLENGE_SALT, compress=True)


def _user_from_challenge(value, purpose):
    try:
        payload = signing.loads(value, salt=CHALLENGE_SALT, max_age=CHALLENGE_MAX_AGE)
    except signing.BadSignature:
        return None
    if payload.get("purpose") != purpose:
        return None
    return User.objects.filter(pk=payload.get("user_id"), is_active=True).first()


def _auth_response(tokens, *, request=None, status_code=200):
    if not getattr(settings, "AUTH_COOKIE_MODE", False):
        return Response(tokens, status=status_code)
    response = Response({"cookie_auth": True}, status=status_code)
    secure = bool(getattr(settings, "SESSION_COOKIE_SECURE", False))
    samesite = getattr(settings, "AUTH_COOKIE_SAMESITE", "Strict")
    response.set_cookie(getattr(settings, "AUTH_ACCESS_COOKIE", "grc_access"), tokens["access"], max_age=15*60, httponly=True, secure=secure, samesite=samesite, path="/")
    response.set_cookie(getattr(settings, "AUTH_REFRESH_COOKIE", "grc_refresh"), tokens["refresh"], max_age=8*60*60, httponly=True, secure=secure, samesite=samesite, path="/api/v1/auth/token/refresh")
    if request is not None:
        response.set_cookie(getattr(settings, "CSRF_COOKIE_NAME", "csrftoken"), get_token(request), max_age=8*60*60, httponly=False, secure=secure, samesite=samesite, path="/")
    return response


class CookieTokenRefreshView(TokenRefreshView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"

    def post(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        from_cookie = not data.get("refresh")
        if from_cookie:
            data["refresh"] = request.COOKIES.get(getattr(settings, "AUTH_REFRESH_COOKIE", "grc_refresh"), "")
            if getattr(settings, "AUTH_COOKIE_MODE", False):
                enforce_csrf(request)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if not getattr(settings, "AUTH_COOKIE_MODE", False):
            return Response(payload)
        response = Response({"cookie_auth": True})
        response.set_cookie(getattr(settings, "AUTH_ACCESS_COOKIE", "grc_access"), payload["access"], max_age=15*60, httponly=True, secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)), samesite=getattr(settings, "AUTH_COOKIE_SAMESITE", "Strict"), path="/")
        return response


class LogoutView(APIView):
    def post(self, request):
        response = Response({"logged_out": True})
        response.delete_cookie(getattr(settings, "AUTH_ACCESS_COOKIE", "grc_access"), path="/")
        response.delete_cookie(getattr(settings, "AUTH_REFRESH_COOKIE", "grc_refresh"), path="/api/v1/auth/token/refresh")
        record_audit_event(request.user, None, "auth.logout", "user", request=request)
        return response


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        username = str(request.data.get("username", "")).strip()
        password = request.data.get("password", "")
        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            record_audit_event(None, None, "auth.login", "user", metadata={"username": username, "result": "failed"}, outcome="failure", request=request)
            return Response({"code": "INVALID_CREDENTIALS", "message": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)

        active_device = MFADevice.objects.filter(user=user, is_active=True).first()
        if active_device:
            challenge = _challenge(user, "verify")
            record_audit_event(user, None, "auth.mfa_challenge", "user", metadata={"result": "required"}, request=request)
            return Response({"code": "MFA_REQUIRED", "mfa_required": True, "challenge": challenge}, status=status.HTTP_202_ACCEPTED)

        if tenant_requires_mfa(user):
            challenge = _challenge(user, "enroll")
            record_audit_event(user, None, "auth.mfa_enrollment_required", "user", request=request)
            return Response({"code": "MFA_SETUP_REQUIRED", "mfa_setup_required": True, "challenge": challenge}, status=status.HTTP_428_PRECONDITION_REQUIRED)

        tokens = _issue_tokens(user)
        record_audit_event(user, None, "auth.login", "user", metadata={"username": username, "result": "success"}, request=request)
        return _auth_response(tokens, request=request)


class MFAVerifyLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mfa"

    def post(self, request):
        user = _user_from_challenge(request.data.get("challenge", ""), "verify")
        if not user:
            return Response({"code": "INVALID_MFA_CHALLENGE", "message": "MFA challenge is invalid or expired."}, status=401)
        device = MFADevice.objects.filter(user=user, is_active=True).first()
        if not device or not verify_mfa_device_once(device, request.data.get("otp")):
            record_audit_event(user, None, "auth.mfa_verify", "user", metadata={"result": "failed"}, outcome="failure", request=request)
            return Response({"code": "INVALID_OTP", "message": "The verification code is invalid."}, status=401)
        tokens = _issue_tokens(user)
        record_audit_event(user, None, "auth.login", "user", metadata={"result": "success_mfa"}, request=request)
        return _auth_response(tokens, request=request)


class MFAEnrollChallengeView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mfa"

    def post(self, request):
        user = _user_from_challenge(request.data.get("challenge", ""), "enroll")
        if not user:
            return Response({"code": "INVALID_MFA_CHALLENGE", "message": "Enrollment challenge is invalid or expired."}, status=401)
        device, secret, uri = create_pending_mfa_device(user)
        next_challenge = _challenge(user, "enroll_verify")
        record_audit_event(user, None, "auth.mfa_enroll_start", "mfa_device", device.id, request=request)
        return Response({"device_id": str(device.id), "secret": secret, "otpauth_uri": uri, "challenge": next_challenge})


class MFAEnrollVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mfa"

    def post(self, request):
        user = _user_from_challenge(request.data.get("challenge", ""), "enroll_verify")
        if not user:
            return Response({"code": "INVALID_MFA_CHALLENGE", "message": "Enrollment challenge is invalid or expired."}, status=401)
        device = MFADevice.objects.filter(user=user, id=request.data.get("device_id"), is_active=False).first()
        if not device or not verify_mfa_device_once(device, request.data.get("otp")):
            return Response({"code": "INVALID_OTP", "message": "The verification code is invalid."}, status=400)
        device.is_active = True
        device.confirmed_at = timezone.now()
        device.save(update_fields=["is_active", "confirmed_at", "updated_at"])
        tokens = _issue_tokens(user)
        record_audit_event(user, None, "auth.mfa_enroll_complete", "mfa_device", device.id, request=request)
        response = _auth_response(tokens, request=request)
        if getattr(settings, "AUTH_COOKIE_MODE", False):
            response.data = {"cookie_auth": True, "mfa_enabled": True}
        else:
            response.data = {**tokens, "mfa_enabled": True}
        return response


class MFAStatusView(APIView):
    def get(self, request):
        devices = MFADevice.objects.filter(user=request.user, is_active=True)
        return Response({"enabled": devices.exists(), "devices": [{"id": str(d.id), "name": d.name, "last_used_at": d.last_used_at} for d in devices]})


class MFASetupView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mfa"

    def post(self, request):
        device, secret, uri = create_pending_mfa_device(request.user, str(request.data.get("name", "Authenticator"))[:100])
        record_audit_event(request.user, None, "auth.mfa_setup", "mfa_device", device.id, request=request)
        return Response({"device_id": str(device.id), "secret": secret, "otpauth_uri": uri})


class MFAConfirmView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mfa"

    def post(self, request):
        device = MFADevice.objects.filter(user=request.user, id=request.data.get("device_id"), is_active=False).first()
        if not device or not verify_mfa_device_once(device, request.data.get("otp")):
            return Response({"code": "INVALID_OTP", "message": "The verification code is invalid."}, status=400)
        device.is_active = True
        device.confirmed_at = timezone.now()
        device.save(update_fields=["is_active", "confirmed_at", "updated_at"])
        record_audit_event(request.user, None, "auth.mfa_enable", "mfa_device", device.id, request=request)
        return Response({"enabled": True})


class MFADisableView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mfa"

    def post(self, request):
        device = MFADevice.objects.filter(user=request.user, is_active=True).first()
        if not device or not verify_mfa_device_once(device, request.data.get("otp")):
            return Response({"code": "INVALID_OTP", "message": "A valid OTP is required to disable MFA."}, status=400)
        MFADevice.objects.filter(user=request.user, is_active=True).update(is_active=False, updated_at=timezone.now())
        record_audit_event(request.user, None, "auth.mfa_disable", "user", request=request)
        return Response({"enabled": False})
