from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.frameworks.models import Requirement
from apps.frameworks.services import lock_framework_version
from .models import Assessment, AssessmentItem

DEFAULT_STATUS_SCORES = {
    AssessmentItem.Status.COMPLIANT: Decimal("100"),
    AssessmentItem.Status.PARTIAL: Decimal("50"),
    AssessmentItem.Status.NON_COMPLIANT: Decimal("0"),
    AssessmentItem.Status.COMPENSATING: Decimal("75"),
}


def _visible_version_for_tenant(version, tenant):
    framework = version.framework
    return framework.tenant_id in {None, tenant.id} and not version.deleted_at and version.status == "active"


@transaction.atomic
def create_assessment(*, tenant, framework_version, title, assessment_type, owner, organization_unit=None, start_date=None, due_date=None, metadata=None):
    if not _visible_version_for_tenant(framework_version, tenant):
        raise ValidationError({"framework_version": "Framework version is not visible to this tenant."})
    if organization_unit and organization_unit.tenant_id != tenant.id:
        raise ValidationError({"organization_unit": "Organization unit must belong to tenant."})
    if framework_version.framework.tenant_id == tenant.id and not framework_version.is_locked:
        lock_framework_version(framework_version, tenant)
        framework_version.refresh_from_db()
    assessment = Assessment.objects.create(
        tenant=tenant,
        framework_version=framework_version,
        organization_unit=organization_unit,
        title=title,
        assessment_type=assessment_type,
        owner=owner,
        start_date=start_date,
        due_date=due_date,
        status=Assessment.Status.IN_PROGRESS,
        metadata=metadata or {},
    )
    requirements = Requirement.objects.filter(
        framework_version=framework_version,
        assessable=True,
        deleted_at__isnull=True,
    ).order_by("sort_order", "code")
    AssessmentItem.objects.bulk_create([
        AssessmentItem(
            assessment=assessment,
            requirement=req,
            requirement_code_snapshot=req.code,
            requirement_title_snapshot=req.title,
            requirement_body_snapshot=req.body,
            weight_snapshot=req.weight,
        ) for req in requirements
    ])
    recalculate_assessment(assessment)
    return assessment


def status_score_map(assessment):
    custom = (assessment.metadata or {}).get("status_scores", {})
    mapping = dict(DEFAULT_STATUS_SCORES)
    for key, value in custom.items():
        try:
            mapping[key] = Decimal(str(value))
        except Exception:
            continue
    return mapping


def recalculate_assessment(assessment):
    items = list(assessment.items.filter(deleted_at__isnull=True))
    if not items:
        assessment.progress_percent = Decimal("0")
        assessment.overall_score = None
        assessment.save(update_fields=["progress_percent", "overall_score", "updated_at"])
        return assessment
    completed = [x for x in items if x.status != AssessmentItem.Status.NOT_ASSESSED]
    progress = (Decimal(len(completed)) / Decimal(len(items))) * Decimal("100")
    factors = status_score_map(assessment)
    numerator = Decimal("0")
    denominator = Decimal("0")
    for item in items:
        if item.status in {AssessmentItem.Status.NOT_ASSESSED, AssessmentItem.Status.NOT_APPLICABLE}:
            continue
        weight = item.weight_snapshot or Decimal("1")
        value = item.score if item.score is not None else factors.get(item.status)
        if value is None:
            continue
        numerator += Decimal(value) * weight
        denominator += Decimal("100") * weight
    score = (numerator / denominator) * Decimal("100") if denominator else None
    assessment.progress_percent = progress.quantize(Decimal("0.001"))
    assessment.overall_score = score.quantize(Decimal("0.001")) if score is not None else None
    assessment.save(update_fields=["progress_percent", "overall_score", "updated_at"])
    return assessment
