from rest_framework.routers import DefaultRouter
from .views import OrganizationUnitViewSet

router = DefaultRouter()
router.register("organization-units", OrganizationUnitViewSet, basename="organization-unit")
urlpatterns = router.urls
