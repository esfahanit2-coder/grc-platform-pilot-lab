import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OperationalSignal",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("key", models.CharField(max_length=80, unique=True)),
                ("status", models.CharField(choices=[("ok", "OK"), ("warning", "Warning"), ("critical", "Critical")], max_length=16)),
                ("source", models.CharField(max_length=120)),
                ("observed_at", models.DateTimeField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.AddIndex(
            model_name="operationalsignal",
            index=models.Index(fields=["status", "observed_at"], name="common_ops_status_obs_idx"),
        ),
    ]
