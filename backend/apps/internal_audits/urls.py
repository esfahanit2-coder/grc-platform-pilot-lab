from rest_framework.routers import DefaultRouter
from .views import AuditPlanViewSet,AuditEngagementViewSet,AuditTeamMemberViewSet,WorkpaperViewSet
r=DefaultRouter();r.register('audit-plans',AuditPlanViewSet,basename='audit-plan');r.register('audits',AuditEngagementViewSet,basename='audit-engagement');r.register('audit-team-members',AuditTeamMemberViewSet,basename='audit-team-member');r.register('audit-workpapers',WorkpaperViewSet,basename='audit-workpaper');urlpatterns=r.urls
