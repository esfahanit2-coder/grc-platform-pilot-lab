from django.urls import include,path
from rest_framework.routers import DefaultRouter
from .views import RiskCategoryViewSet,RiskControlViewSet,RiskMethodologyViewSet,RiskTreatmentViewSet,RiskViewSet
router=DefaultRouter();router.register("risk-categories",RiskCategoryViewSet,basename="risk-category");router.register("risk-methodologies",RiskMethodologyViewSet,basename="risk-methodology");router.register("risks",RiskViewSet,basename="risk");router.register("risk-controls",RiskControlViewSet,basename="risk-control");router.register("risk-treatments",RiskTreatmentViewSet,basename="risk-treatment")
urlpatterns=[path("",include(router.urls))]
