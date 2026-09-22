import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q
from django.db.models.deletion import PROTECT


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_sync_index_names"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditChainState",
            fields=[
                (
                    "scope_key",
                    models.CharField(max_length=80, primary_key=True, serialize=False),
                ),
                ("sequence", models.PositiveBigIntegerField(default=0)),
                ("last_hash", models.CharField(default="0" * 64, max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=PROTECT,
                        related_name="audit_chain_states",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Audit chain state",
                "verbose_name_plural": "Audit chain states",
            },
        ),
        migrations.AlterModelOptions(
            name="auditevent",
            options={
                "ordering": ["-created_at"],
                "base_manager_name": "system_objects",
                "default_manager_name": "objects",
            },
        ),
        migrations.AlterModelManagers(
            name="auditevent",
            managers=[
                ("objects", models.Manager()),
                ("system_objects", models.Manager()),
            ],
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="created_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                editable=False,
            ),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="chain_sequence",
            field=models.PositiveBigIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="previous_hash",
            field=models.CharField(default="0" * 64, editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="event_hash",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="integrity_key_id",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["tenant", "chain_sequence"],
                name="audit_audit_tenant__9bc645_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditevent",
            constraint=models.UniqueConstraint(
                condition=Q(tenant__isnull=False, chain_sequence__gt=0),
                fields=("tenant", "chain_sequence"),
                name="audit_tenant_chain_sequence_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditevent",
            constraint=models.UniqueConstraint(
                condition=Q(tenant__isnull=True, chain_sequence__gt=0),
                fields=("chain_sequence",),
                name="audit_global_chain_sequence_unique",
            ),
        ),
    ]
