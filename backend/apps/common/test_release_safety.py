from django.test import SimpleTestCase

from apps.common.release_safety import analyze_migration_plan


class ReversibleOperation:
    reversible = True


class IrreversibleOperation:
    reversible = False


class FakeMigration:
    def __init__(self, app_label, name, operations):
        self.app_label = app_label
        self.name = name
        self.operations = operations


class ReleaseMigrationSafetyTests(SimpleTestCase):
    def test_reversible_forward_plan_is_safe(self):
        plan = [
            (FakeMigration("risks", "0002_safe", [ReversibleOperation()]), False),
            (FakeMigration("controls", "0003_safe", [ReversibleOperation()]), False),
        ]

        result = analyze_migration_plan(plan)

        self.assertTrue(result.rollback_safe)
        self.assertEqual(result.blockers, [])
        self.assertEqual(len(result.migrations), 2)
        self.assertEqual(result.migrations[0]["direction"], "forward")

    def test_irreversible_operation_is_reported(self):
        plan = [
            (FakeMigration("risks", "0002_unsafe", [IrreversibleOperation()]), False),
        ]

        result = analyze_migration_plan(plan)

        self.assertFalse(result.rollback_safe)
        self.assertEqual(result.blockers[0]["migration"], "risks.0002_unsafe")
        self.assertEqual(result.blockers[0]["operation_index"], 0)
        self.assertEqual(result.blockers[0]["reason"], "irreversible_operation")

    def test_backward_step_in_upgrade_plan_is_reported(self):
        plan = [
            (FakeMigration("risks", "0002_branch", [ReversibleOperation()]), True),
        ]

        result = analyze_migration_plan(plan)

        self.assertFalse(result.rollback_safe)
        self.assertEqual(result.blockers[0]["reason"], "upgrade_plan_contains_backward_step")
        self.assertEqual(result.migrations[0]["direction"], "backward")
