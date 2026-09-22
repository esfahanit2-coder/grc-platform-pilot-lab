from django.urls import include,path
from rest_framework.routers import DefaultRouter
from .views import FindingViewSet
router=DefaultRouter();router.register("findings",FindingViewSet,basename="finding")
urlpatterns=[path("",include(router.urls))]
