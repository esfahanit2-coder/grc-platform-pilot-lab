from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0008_sync_index_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="mfadevice",
            name="last_used_step",
            field=models.BigIntegerField(blank=True, editable=False, null=True),
        ),
    ]
