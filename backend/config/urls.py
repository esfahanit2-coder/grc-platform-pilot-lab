from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/auth/", include("apps.tenancy.auth_urls")),
    path("api/v1/", include("apps.tenancy.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.identity.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.frameworks.urls")),
    path("api/v1/", include("apps.controls.urls")),
    path("api/v1/", include("apps.assets.urls")),
    path("api/v1/", include("apps.actions.urls")),
    path("api/v1/", include("apps.risks.urls")),
    path("api/v1/", include("apps.assessments.urls")),
    path("api/v1/", include("apps.evidence.urls")),
    path("api/v1/", include("apps.findings.urls")),
    path("api/v1/", include("apps.internal_audits.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.reporting.urls")),
    path("api/v1/", include("apps.ai_gateway.urls")),
    path("api/v1/", include("apps.workflows.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.connectors.urls")),
]
