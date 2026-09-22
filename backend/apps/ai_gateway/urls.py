from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AIProviderViewSet, AIInteractionViewSet, AISuggestionViewSet, KnowledgeChunkViewSet, AIAssistantViewSet
router=DefaultRouter()
router.register("ai/providers",AIProviderViewSet,basename="ai-provider")
router.register("ai/interactions",AIInteractionViewSet,basename="ai-interaction")
router.register("ai/suggestions",AISuggestionViewSet,basename="ai-suggestion")
router.register("ai/knowledge",KnowledgeChunkViewSet,basename="ai-knowledge")
router.register("ai/assist",AIAssistantViewSet,basename="ai-assist")
urlpatterns=[path("",include(router.urls))]
