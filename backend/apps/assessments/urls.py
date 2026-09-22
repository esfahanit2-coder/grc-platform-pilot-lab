from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AssessmentItemViewSet, AssessmentViewSet
router=DefaultRouter();router.register("assessments",AssessmentViewSet,basename="assessment");router.register("assessment-items",AssessmentItemViewSet,basename="assessment-item")
urlpatterns=[path("",include(router.urls))]
