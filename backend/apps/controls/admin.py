from django.contrib import admin
from .models import Control, ControlCategory, ControlImplementation, ControlRequirement
admin.site.register([ControlCategory, Control, ControlRequirement, ControlImplementation])
