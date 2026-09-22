from django.urls import path
from .views import AuditEventExportView, AuditEventListView

urlpatterns = [
    path("audit-events/", AuditEventListView.as_view(), name="audit-event-list"),
    path("audit-events/export/", AuditEventExportView.as_view(), name="audit-event-export"),
]
