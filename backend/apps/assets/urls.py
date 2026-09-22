from django.urls import include,path
from rest_framework.routers import DefaultRouter
from .views import AssetDependencyViewSet,AssetViewSet
router=DefaultRouter();router.register("assets",AssetViewSet,basename="asset");router.register("asset-dependencies",AssetDependencyViewSet,basename="asset-dependency")
urlpatterns=[path("",include(router.urls))]
