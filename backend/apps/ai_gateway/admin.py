from django.contrib import admin
from .models import AIProviderConfig, AIInteraction, AISuggestion, KnowledgeChunk
admin.site.register([AIProviderConfig, AIInteraction, AISuggestion, KnowledgeChunk])
