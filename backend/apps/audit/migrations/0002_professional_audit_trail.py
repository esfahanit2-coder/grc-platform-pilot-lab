import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [
        migrations.AddField(model_name="auditevent", name="actor_username", field=models.CharField(blank=True, default="", max_length=150), preserve_default=False),
        migrations.AddField(model_name="auditevent", name="category", field=models.CharField(default="application", max_length=64)),
        migrations.AddField(model_name="auditevent", name="outcome", field=models.CharField(choices=[("success", "Success"), ("failure", "Failure"), ("denied", "Denied")], default="success", max_length=16)),
        migrations.AddField(model_name="auditevent", name="object_repr", field=models.CharField(blank=True, default="", max_length=255), preserve_default=False),
        migrations.AddField(model_name="auditevent", name="old_data", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="auditevent", name="new_data", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="auditevent", name="http_method", field=models.CharField(blank=True, default="", max_length=12), preserve_default=False),
        migrations.AddField(model_name="auditevent", name="path", field=models.CharField(blank=True, default="", max_length=500), preserve_default=False),
        migrations.AlterField(model_name="auditevent", name="request_id", field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["tenant", "actor", "created_at"], name="audit_audit_tenant__b3564d_idx")),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["tenant", "object_type", "object_id"], name="audit_audit_tenant__a0a4fc_idx")),
    ]
