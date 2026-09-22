from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def bootstrap_defaults(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Role = apps.get_model("identity", "Role")
    RolePermission = apps.get_model("identity", "RolePermission")
    UserRoleScope = apps.get_model("identity", "UserRoleScope")
    Tenant = apps.get_model("tenancy", "Tenant")
    Membership = apps.get_model("tenancy", "TenantMembership")

    catalog = [
        ("tenant.view", "tenant", "View tenant settings"),
        ("tenant.manage", "tenant", "Manage tenant settings"),
        ("membership.view", "identity", "View tenant users"),
        ("membership.manage", "identity", "Manage tenant users"),
        ("role.view", "identity", "View roles and permissions"),
        ("role.manage", "identity", "Manage roles and assignments"),
        ("organization.view", "organization", "View organization structure"),
        ("organization.manage", "organization", "Manage organization structure"),
        ("audit.view", "audit", "View audit trail"),
        ("security.view", "security", "View security configuration"),
        ("security.manage", "security", "Manage security configuration"),
    ]
    permissions = {}
    for code, module, description in catalog:
        permissions[code], _ = Permission.objects.get_or_create(
            code=code,
            defaults={"module": module, "name": code.replace(".", " ").title(), "description": description},
        )

    role_defs = {
        "tenant_admin": [code for code, _, _ in catalog],
        "grc_manager": ["tenant.view", "membership.view", "role.view", "organization.view", "organization.manage", "audit.view", "security.view"],
        "auditor": ["tenant.view", "organization.view", "audit.view"],
        "viewer": ["tenant.view", "organization.view"],
    }
    names = {"tenant_admin": "Tenant Administrator", "grc_manager": "GRC Manager", "auditor": "Auditor", "viewer": "Viewer"}
    for tenant in Tenant.objects.all():
        roles = {}
        for code, permission_codes in role_defs.items():
            role, _ = Role.objects.get_or_create(tenant=tenant, code=code, defaults={"name": names[code], "is_system": True})
            roles[code] = role
            for permission_code in permission_codes:
                RolePermission.objects.get_or_create(role=role, permission=permissions[permission_code])
        for membership in Membership.objects.filter(tenant=tenant, role_code="admin", is_active=True):
            UserRoleScope.objects.get_or_create(
                user_id=membership.user_id,
                tenant=tenant,
                role=roles["tenant_admin"],
                organization_unit=None,
                defaults={"is_active": True},
            )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenancy", "0001_initial"),
        ("organizations", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.CharField(max_length=120, unique=True)),
                ("module", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["module", "code"]},
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("is_system", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="roles", to="tenancy.tenant")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="MFADevice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(default="Authenticator", max_length=100)),
                ("encrypted_secret", models.TextField()),
                ("is_active", models.BooleanField(default=False)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mfa_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-is_active", "created_at"]},
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="identity.permission")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="identity.role")),
            ],
        ),
        migrations.AddField(
            model_name="role",
            name="permissions",
            field=models.ManyToManyField(related_name="roles", through="identity.RolePermission", to="identity.permission"),
        ),
        migrations.CreateModel(
            name="UserRoleScope",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("organization_unit", models.ForeignKey(blank=True, help_text="Null means the whole tenant.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="role_assignments", to="organizations.organizationunit")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="identity.role")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_role_scopes", to="tenancy.tenant")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grc_role_scopes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name="role", constraint=models.UniqueConstraint(fields=("tenant", "code"), name="uq_role_tenant_code")),
        migrations.AddConstraint(model_name="rolepermission", constraint=models.UniqueConstraint(fields=("role", "permission"), name="uq_role_permission")),
        migrations.AddConstraint(model_name="userrolescope", constraint=models.UniqueConstraint(fields=("user", "tenant", "role", "organization_unit"), name="uq_user_role_scope")),
        migrations.AddConstraint(model_name="userrolescope", constraint=models.UniqueConstraint(condition=models.Q(organization_unit__isnull=True), fields=("user", "tenant", "role"), name="uq_user_role_whole_tenant")),
        migrations.AddIndex(model_name="permission", index=models.Index(fields=["module", "is_active"], name="identity_pe_module_ef8480_idx")),
        migrations.AddIndex(model_name="role", index=models.Index(fields=["tenant", "is_active"], name="identity_ro_tenant_4f6959_idx")),
        migrations.AddIndex(model_name="userrolescope", index=models.Index(fields=["tenant", "user", "is_active"], name="identity_us_tenant_29b67b_idx")),
        migrations.AddIndex(model_name="userrolescope", index=models.Index(fields=["tenant", "role", "is_active"], name="identity_us_tenant_59d07a_idx")),
        migrations.AddIndex(model_name="mfadevice", index=models.Index(fields=["user", "is_active"], name="identity_mf_user_id_ed8518_idx")),
        migrations.RunPython(bootstrap_defaults, migrations.RunPython.noop),
    ]
