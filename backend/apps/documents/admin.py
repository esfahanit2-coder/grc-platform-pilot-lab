from django.contrib import admin
from .models import Document,DocumentVersion,DocumentApproval,DocumentLink,ReportTemplate
admin.site.register([Document,DocumentVersion,DocumentApproval,DocumentLink,ReportTemplate])
