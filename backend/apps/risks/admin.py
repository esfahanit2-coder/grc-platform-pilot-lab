from django.contrib import admin
from .models import Risk,RiskCategory,RiskControl,RiskEvaluation,RiskMethodology,RiskTreatment
admin.site.register([RiskCategory,RiskMethodology,Risk,RiskEvaluation,RiskControl,RiskTreatment])
