from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=255)),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("tenant_type", models.CharField(choices=[("enterprise", "Enterprise"), ("holding", "Holding"), ("consulting", "Consulting Company"), ("saas", "SaaS Customer")], default="enterprise", max_length=20)),
                ("status", models.CharField(default="active", max_length=20)),
                ("default_language", models.CharField(default="fa", max_length=10)),
                ("timezone", models.CharField(default="Asia/Tehran", max_length=64)),
                ("settings", models.JSONField(blank=True, default=dict)),
            ],
        ),
        migrations.CreateModel(
            name="TenantMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("role_code", models.CharField(default="member", max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="tenancy.tenant")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tenant_memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="tenantmembership",
            constraint=models.UniqueConstraint(fields=("tenant", "user"), name="uq_tenant_membership_user"),
        ),
    ]
