from django.urls import include,path
from rest_framework.routers import DefaultRouter
from .views import WorkflowDefinitionViewSet,WorkflowInstanceViewSet
router=DefaultRouter();router.register('workflows/definitions',WorkflowDefinitionViewSet,basename='workflow-definition');router.register('workflows/instances',WorkflowInstanceViewSet,basename='workflow-instance')
urlpatterns=[path('',include(router.urls))]
