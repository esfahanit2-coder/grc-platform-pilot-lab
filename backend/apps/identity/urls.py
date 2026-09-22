from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import PermissionListView, RoleAssignmentViewSet, RoleViewSet, TenantUserViewSet

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("tenant-users", TenantUserViewSet, basename="tenant-user")
router.register("role-assignments", RoleAssignmentViewSet, basename="role-assignment")

urlpatterns = [
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("", include(router.urls)),
]
