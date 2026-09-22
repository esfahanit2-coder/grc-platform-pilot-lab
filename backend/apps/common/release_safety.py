from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MigrationSafetyResult:
    migrations: list[dict[str, Any]]
    blockers: list[dict[str, Any]]

    @property
    def rollback_safe(self) -> bool:
        return not self.blockers


def _operation_name(operation: object) -> str:
    return f"{operation.__class__.__module__}.{operation.__class__.__name__}"


def analyze_migration_plan(plan: Iterable[tuple[object, bool]]) -> MigrationSafetyResult:
    """Describe a Django migration plan without executing it.

    A release upgrade is considered rollback-safe only when the plan contains
    forward steps and every operation in those new migrations advertises
    Django-level reversibility. Operational rollback still uses a pre-upgrade
    backup; this check prevents us from silently promising schema reversal when
    Django itself cannot reverse an operation.
    """

    migrations: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    for migration, backwards in plan:
        app_label = str(getattr(migration, "app_label", "unknown"))
        name = str(getattr(migration, "name", "unknown"))
        migration_id = f"{app_label}.{name}"
        operations: list[dict[str, Any]] = []

        if backwards:
            blockers.append(
                {
                    "migration": migration_id,
                    "reason": "upgrade_plan_contains_backward_step",
                }
            )

        for index, operation in enumerate(getattr(migration, "operations", ())):
            reversible = bool(getattr(operation, "reversible", True))
            row = {
                "index": index,
                "operation": _operation_name(operation),
                "reversible": reversible,
            }
            operations.append(row)
            if not reversible:
                blockers.append(
                    {
                        "migration": migration_id,
                        "operation_index": index,
                        "operation": row["operation"],
                        "reason": "irreversible_operation",
                    }
                )

        migrations.append(
            {
                "migration": migration_id,
                "direction": "backward" if backwards else "forward",
                "operations": operations,
            }
        )

    return MigrationSafetyResult(migrations=migrations, blockers=blockers)
