from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from .verification import verify_audit_scope


@override_settings(
    APP_ENV="test",
    AUDIT_INTEGRITY_KEY="migration-test-audit-integrity-key-at-least-32-bytes-long",
    AUDIT_INTEGRITY_KEY_ID="migration-test-v1",
)
class AuditIntegrityBackfillMigrationTests(TransactionTestCase):
    migrate_from = [("audit", "0003_sync_index_names")]
    migrate_to = [("audit", "0005_seal_existing_audit_history")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        self.addCleanup(self._restore_latest_schema)

        old_apps = executor.loader.project_state(self.migrate_from).apps
        Tenant = old_apps.get_model("tenancy", "Tenant")
        AuditEvent = old_apps.get_model("audit", "AuditEvent")

        tenant = Tenant.objects.create(name="Legacy Audit Tenant", code="legacy-audit-tenant")
        self.tenant_id = tenant.id
        AuditEvent.objects.create(
            tenant_id=tenant.id,
            action="legacy.create",
            object_type="tenant",
            object_id=tenant.id,
            object_repr="legacy-one",
        )
        AuditEvent.objects.create(
            tenant_id=tenant.id,
            action="legacy.update",
            object_type="tenant",
            object_id=tenant.id,
            object_repr="legacy-two",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)

    def _restore_latest_schema(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_events_are_resealed_into_one_contiguous_chain(self):
        executor = MigrationExecutor(connection)
        migrated_apps = executor.loader.project_state(self.migrate_to).apps
        AuditEvent = migrated_apps.get_model("audit", "AuditEvent")
        AuditChainState = migrated_apps.get_model("audit", "AuditChainState")

        events = list(
            AuditEvent.objects.filter(tenant_id=self.tenant_id).order_by("chain_sequence")
        )
        self.assertEqual([event.chain_sequence for event in events], [1, 2])
        self.assertEqual(events[0].previous_hash, "0" * 64)
        self.assertTrue(events[0].event_hash)
        self.assertEqual(events[1].previous_hash, events[0].event_hash)
        self.assertTrue(events[1].event_hash)
        self.assertEqual(events[0].integrity_key_id, "migration-test-v1")
        self.assertEqual(events[1].integrity_key_id, "migration-test-v1")

        state = AuditChainState.objects.get(scope_key=f"tenant:{self.tenant_id}")
        self.assertEqual(state.sequence, 2)
        self.assertEqual(state.last_hash, events[1].event_hash)

        runtime_result = verify_audit_scope(self.tenant_id)
        self.assertTrue(runtime_result.ok, runtime_result.as_dict())
