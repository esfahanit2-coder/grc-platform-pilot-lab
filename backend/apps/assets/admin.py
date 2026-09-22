from django.contrib import admin
from .models import Asset,AssetDependency
admin.site.register([Asset,AssetDependency])
