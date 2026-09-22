from django.contrib import admin
from .models import Framework, FrameworkVersion, Requirement, RequirementTranslation, RequirementMapping

admin.site.register(Framework)
admin.site.register(FrameworkVersion)
admin.site.register(Requirement)
admin.site.register(RequirementTranslation)
admin.site.register(RequirementMapping)
