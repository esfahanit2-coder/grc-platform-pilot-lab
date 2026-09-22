from django.urls import include,path
from rest_framework.routers import DefaultRouter
from .views import EvidenceLinkViewSet,EvidenceViewSet
router=DefaultRouter();router.register("evidence",EvidenceViewSet,basename="evidence");router.register("evidence-links",EvidenceLinkViewSet,basename="evidence-link")
urlpatterns=[path("",include(router.urls))]
