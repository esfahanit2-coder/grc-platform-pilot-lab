from django.contrib import admin
from .models import AuditPlan,AuditEngagement,AuditTeamMember,Workpaper
admin.site.register([AuditPlan,AuditEngagement,AuditTeamMember,Workpaper])
