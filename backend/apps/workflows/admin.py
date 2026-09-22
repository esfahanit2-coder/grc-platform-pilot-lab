from django.contrib import admin
from .models import WorkflowDefinition,WorkflowState,WorkflowTransition,WorkflowInstance,WorkflowEvent
admin.site.register([WorkflowDefinition,WorkflowState,WorkflowTransition,WorkflowInstance,WorkflowEvent])
