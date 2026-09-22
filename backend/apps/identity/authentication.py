from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")


class CookieOrHeaderJWTAuthentication(JWTAuthentication):
    """Prefer Authorization header; fall back to an HttpOnly access cookie with CSRF enforcement."""
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)
        raw_token = request.COOKIES.get(getattr(settings, "AUTH_ACCESS_COOKIE", "grc_access"))
        if not raw_token:
            return None
        enforce_csrf(request)
        validated = self.get_validated_token(raw_token.encode("utf-8") if isinstance(raw_token, str) else raw_token)
        return self.get_user(validated), validated
