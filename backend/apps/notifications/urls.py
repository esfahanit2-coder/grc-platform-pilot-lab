from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import NotificationDeliveryViewSet, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")
router.register(
    "notification-deliveries",
    NotificationDeliveryViewSet,
    basename="notification-delivery",
)
urlpatterns = [path("", include(router.urls))]
