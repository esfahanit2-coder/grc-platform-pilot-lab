from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet,DocumentVersionViewSet,DocumentApprovalViewSet,ReportTemplateViewSet,SoAViewSet
r=DefaultRouter();r.register('documents',DocumentViewSet,basename='document');r.register('document-versions',DocumentVersionViewSet,basename='document-version');r.register('document-approvals',DocumentApprovalViewSet,basename='document-approval');r.register('report-templates',ReportTemplateViewSet,basename='report-template');urlpatterns=r.urls+[path('reports/soa/<uuid:assessment_id>/',SoAViewSet.as_view({'get':'generate'}),name='soa-report')]
