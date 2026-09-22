from django.contrib import admin
from .models import MFADevice, Permission, Role, RolePermission, UserRoleScope

admin.site.register(Permission)
admin.site.register(Role)
admin.site.register(RolePermission)
admin.site.register(UserRoleScope)
admin.site.register(MFADevice)
