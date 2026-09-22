from django.urls import path

from .views import FormalReportExportView, FormalReportPreviewView, ManagementDashboardView, ReportCatalogView, TemplateRenderView
from .work_center import WorkCenterView

urlpatterns = [
    path("dashboard/management/", ManagementDashboardView.as_view(), name="management-dashboard"),
    path("work-center/", WorkCenterView.as_view(), name="work-center"),
    path("reports/render-template/", TemplateRenderView.as_view(), name="report-template-render"),
    path("reports/catalog/", ReportCatalogView.as_view(), name="report-catalog"),
    path("reports/preview/", FormalReportPreviewView.as_view(), name="report-preview"),
    path("reports/export/", FormalReportExportView.as_view(), name="report-export"),
]
