from django.urls import path
from .auth_views import (
    LoginView,
    CookieTokenRefreshView,
    LogoutView,
    MFAConfirmView,
    MFADisableView,
    MFAEnrollChallengeView,
    MFAEnrollVerifyView,
    MFASetupView,
    MFAStatusView,
    MFAVerifyLoginView,
)

urlpatterns = [
    path("token", LoginView.as_view(), name="token-obtain-pair"),
    path("token/refresh", CookieTokenRefreshView.as_view(), name="token-refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("mfa/verify-login", MFAVerifyLoginView.as_view(), name="mfa-verify-login"),
    path("mfa/enroll", MFAEnrollChallengeView.as_view(), name="mfa-enroll"),
    path("mfa/enroll/verify", MFAEnrollVerifyView.as_view(), name="mfa-enroll-verify"),
    path("mfa/status", MFAStatusView.as_view(), name="mfa-status"),
    path("mfa/setup", MFASetupView.as_view(), name="mfa-setup"),
    path("mfa/confirm", MFAConfirmView.as_view(), name="mfa-confirm"),
    path("mfa/disable", MFADisableView.as_view(), name="mfa-disable"),
]
