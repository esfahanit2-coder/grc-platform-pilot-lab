from django.urls import path
from .views import CurrentTenantView, MyTenantsView, SecuritySettingsView, TenantProvisionListCreateView

urlpatterns = [
    path("tenants", TenantProvisionListCreateView.as_view(), name="tenant-provision"),
    path("tenants/mine", MyTenantsView.as_view(), name="my-tenants"),
    path("tenant/current", CurrentTenantView.as_view(), name="tenant-current"),
    path("tenant/security", SecuritySettingsView.as_view(), name="tenant-security"),
]
