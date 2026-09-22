from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenancy", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="OrganizationUnit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("unit_type", models.CharField(choices=[("holding", "Holding"), ("company", "Company"), ("business_unit", "Business Unit"), ("department", "Department"), ("site", "Site"), ("team", "Team")], max_length=32)),
                ("code", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=255)),
                ("name_en", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(default="active", max_length=20)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("manager", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="organizations.organizationunit")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="organization_units", to="tenancy.tenant")),
            ],
        ),
        migrations.AddConstraint(
            model_name="organizationunit",
            constraint=models.UniqueConstraint(fields=("tenant", "code"), name="uq_orgunit_tenant_code"),
        ),
        migrations.AddIndex(
            model_name="organizationunit",
            index=models.Index(fields=["tenant", "parent"], name="organizatio_tenant__8f0e13_idx"),
        ),
        migrations.AddIndex(
            model_name="organizationunit",
            index=models.Index(fields=["tenant", "status"], name="organizatio_tenant__a91a95_idx"),
        ),
    ]
