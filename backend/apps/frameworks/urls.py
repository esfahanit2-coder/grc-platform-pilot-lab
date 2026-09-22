from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import FrameworkImportView, FrameworkVersionViewSet, FrameworkViewSet, RequirementMappingViewSet, RequirementViewSet

router = DefaultRouter()
router.register("frameworks", FrameworkViewSet, basename="framework")
router.register("framework-versions", FrameworkVersionViewSet, basename="framework-version")
router.register("requirements", RequirementViewSet, basename="requirement")
router.register("requirement-mappings", RequirementMappingViewSet, basename="requirement-mapping")

urlpatterns = [
    path("frameworks/import/", FrameworkImportView.as_view(), name="framework-import"),
    path("", include(router.urls)),
]
