from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.actions.models import Action
from apps.assessments.models import Assessment, AssessmentItem
from apps.documents.models import DocumentApproval
from apps.findings.models import Finding
from apps.identity.services import (
    accessible_organization_unit_ids,
    has_tenant_permission,
    has_whole_tenant_permission,
)
from apps.internal_audits.models import AuditEngagement, Workpaper
from apps.tenancy.services import resolve_tenant_for_request


DUE_SOON_DAYS = 7


def _permission_scope(user, tenant, permission_code):
    """Return the source module's effective organization scope for one permission.

    ``whole`` deliberately mirrors each source view's treatment of records whose
    organization_unit is null: scoped assignments do not gain access to those
    whole-tenant records through Work Center.
    """

    if not has_tenant_permission(user, tenant, permission_code):
        return None
    whole = has_whole_tenant_permission(user, tenant, permission_code)
    allowed = frozenset(accessible_organization_unit_ids(user, tenant, permission_code))
    return whole, allowed


def _intersect_scopes(*scopes):
    """Intersect permission scopes without broadening whole-tenant semantics."""

    if not scopes or any(scope is None for scope in scopes):
        return None
    if all(scope[0] for scope in scopes):
        return True, frozenset()
    restricted = [set(scope[1]) for scope in scopes if not scope[0]]
    allowed = restricted[0]
    for values in restricted[1:]:
        allowed.intersection_update(values)
    return False, frozenset(allowed)


def _apply_scope(queryset, scope, field="organization_unit_id"):
    if scope is None:
        return queryset.none()
    whole, allowed = scope
    if whole:
        return queryset
    return queryset.filter(**{f"{field}__in": allowed})


def _scope_allows(scope, organization_unit_id):
    if scope is None:
        return False
    whole, allowed = scope
    if organization_unit_id is None:
        return whole
    return whole or organization_unit_id in allowed


def _attention(due_date, today, due_soon_until, is_review):
    if due_date and due_date < today:
        return "overdue"
    if is_review:
        return "review"
    if due_date and today <= due_date <= due_soon_until:
        return "due_soon"
    return "normal"


def _unit_name(obj):
    unit = getattr(obj, "organization_unit", None)
    return getattr(unit, "name", "") if unit else ""


class WorkCenterView(APIView):
    """Aggregate existing assigned/review work without creating parallel state."""

    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        user = request.user
        today = timezone.localdate()
        due_soon_until = today + timedelta(days=DUE_SOON_DAYS)
        items = []

        def add_item(
            *,
            source,
            source_id,
            title,
            subtitle="",
            status="",
            status_label="",
            responsibility="owner",
            priority="",
            due_date=None,
            href,
            organization_unit="",
            is_review=False,
            can_act=False,
        ):
            is_overdue = bool(due_date and due_date < today)
            is_due_soon = bool(due_date and today <= due_date <= due_soon_until)
            items.append(
                {
                    "key": f"{source}:{source_id}:{responsibility}",
                    "source": source,
                    "source_id": str(source_id),
                    "title": title,
                    "subtitle": subtitle,
                    "status": status,
                    "status_label": status_label or status,
                    "responsibility": responsibility,
                    "priority": priority,
                    "due_date": due_date,
                    "organization_unit": organization_unit,
                    "href": href,
                    "can_act": bool(can_act),
                    "is_review": bool(is_review),
                    "is_overdue": is_overdue,
                    "is_due_soon": is_due_soon,
                    "attention": _attention(due_date, today, due_soon_until, is_review),
                }
            )

        # Actions: ownership is always relevant; reviewer responsibility becomes
        # actionable when the Action itself reaches the review state.
        action_view = _permission_scope(user, tenant, "action.view")
        action_manage = _permission_scope(user, tenant, "action.manage")
        if action_view is not None:
            actions = Action.objects.filter(tenant=tenant, deleted_at__isnull=True).exclude(
                status__in=[Action.Status.DONE, Action.Status.CANCELLED]
            ).filter(Q(owner=user) | Q(reviewer=user, status=Action.Status.REVIEW))
            actions = _apply_scope(
                actions.select_related("organization_unit", "owner", "reviewer"),
                action_view,
            )
            for action in actions:
                is_review = action.reviewer_id == user.id and action.status == Action.Status.REVIEW
                add_item(
                    source="action",
                    source_id=action.id,
                    title=action.title,
                    subtitle=action.source_type or "اقدام مستقل",
                    status=action.status,
                    status_label=action.get_status_display(),
                    responsibility="reviewer" if is_review else "owner",
                    priority=action.priority,
                    due_date=action.due_date,
                    href="/actions",
                    organization_unit=_unit_name(action),
                    is_review=is_review,
                    can_act=_scope_allows(action_manage, action.organization_unit_id),
                )

        finding_view = _permission_scope(user, tenant, "finding.view")
        finding_manage = _permission_scope(user, tenant, "finding.manage")
        finding_close = _permission_scope(user, tenant, "finding.close")
        if finding_view is not None:
            findings = Finding.objects.filter(
                tenant=tenant,
                owner=user,
                deleted_at__isnull=True,
            ).exclude(status__in=[Finding.Status.CLOSED, Finding.Status.ACCEPTED])
            findings = _apply_scope(findings.select_related("organization_unit"), finding_view)
            for finding in findings:
                can_act = _scope_allows(finding_manage, finding.organization_unit_id) or _scope_allows(
                    finding_close, finding.organization_unit_id
                )
                add_item(
                    source="finding",
                    source_id=finding.id,
                    title=finding.title,
                    subtitle=finding.get_finding_type_display(),
                    status=finding.status,
                    status_label=finding.get_status_display(),
                    responsibility="owner",
                    priority=finding.severity,
                    due_date=finding.due_date,
                    href=f"/findings/{finding.id}",
                    organization_unit=_unit_name(finding),
                    can_act=can_act,
                )

        assessment_view = _permission_scope(user, tenant, "assessment.view")
        assessment_perform = _permission_scope(user, tenant, "assessment.perform")
        if assessment_view is not None:
            assigned_items = AssessmentItem.objects.filter(
                assessment__tenant=tenant,
                assessment__deleted_at__isnull=True,
                assessment__status__in=[Assessment.Status.DRAFT, Assessment.Status.IN_PROGRESS, Assessment.Status.IN_REVIEW],
                assigned_to=user,
                deleted_at__isnull=True,
            ).exclude(status__in=[AssessmentItem.Status.COMPLIANT, AssessmentItem.Status.NOT_APPLICABLE])
            assigned_items = _apply_scope(
                assigned_items.select_related("assessment__organization_unit", "assessment"),
                assessment_view,
                "assessment__organization_unit_id",
            )
            for item in assigned_items:
                assessment = item.assessment
                add_item(
                    source="assessment_item",
                    source_id=item.id,
                    title=f"{item.requirement_code_snapshot} — {item.requirement_title_snapshot}",
                    subtitle=assessment.title,
                    status=item.status,
                    status_label=item.get_status_display(),
                    responsibility="assignee",
                    due_date=assessment.due_date,
                    href=f"/assessments/{assessment.id}",
                    organization_unit=_unit_name(assessment),
                    can_act=_scope_allows(assessment_perform, assessment.organization_unit_id),
                )

        assessment_review = _permission_scope(user, tenant, "assessment.review")
        assessment_review_visibility = _intersect_scopes(assessment_view, assessment_review)
        if assessment_review_visibility is not None:
            review_assessments = Assessment.objects.filter(
                tenant=tenant,
                status=Assessment.Status.IN_REVIEW,
                deleted_at__isnull=True,
            )
            review_assessments = _apply_scope(
                review_assessments.select_related("organization_unit", "framework_version__framework"),
                assessment_review_visibility,
            )
            for assessment in review_assessments:
                add_item(
                    source="assessment_review",
                    source_id=assessment.id,
                    title=assessment.title,
                    subtitle=f"{assessment.framework_version.framework.name} · {assessment.framework_version.version_code}",
                    status=assessment.status,
                    status_label=assessment.get_status_display(),
                    responsibility="review_queue",
                    due_date=assessment.due_date,
                    href=f"/assessments/{assessment.id}",
                    organization_unit=_unit_name(assessment),
                    is_review=True,
                    can_act=_scope_allows(assessment_review, assessment.organization_unit_id),
                )

        document_view = _permission_scope(user, tenant, "document.view")
        document_approve = _permission_scope(user, tenant, "document.approve")
        if document_view is not None:
            approvals = DocumentApproval.objects.filter(
                version__document__tenant=tenant,
                version__document__deleted_at__isnull=True,
                version__deleted_at__isnull=True,
                approver=user,
                decision=DocumentApproval.Decision.PENDING,
                deleted_at__isnull=True,
            )
            approvals = _apply_scope(
                approvals.select_related("version__document__organization_unit", "version__document"),
                document_view,
                "version__document__organization_unit_id",
            )
            for approval in approvals:
                document = approval.version.document
                add_item(
                    source="document_approval",
                    source_id=approval.id,
                    title=document.title,
                    subtitle=f"{document.code} · نسخه {approval.version.version}",
                    status=approval.decision,
                    status_label=approval.get_decision_display(),
                    responsibility="approver",
                    href="/documents",
                    organization_unit=_unit_name(document),
                    is_review=True,
                    can_act=_scope_allows(document_approve, document.organization_unit_id),
                )

        audit_view = _permission_scope(user, tenant, "internal_audit.view")
        audit_manage = _permission_scope(user, tenant, "internal_audit.manage")
        audit_perform = _permission_scope(user, tenant, "internal_audit.perform")
        audit_review = _permission_scope(user, tenant, "internal_audit.review")
        if audit_view is not None:
            engagements = AuditEngagement.objects.filter(
                tenant=tenant,
                lead_auditor=user,
                deleted_at__isnull=True,
            ).exclude(status__in=[AuditEngagement.Status.COMPLETED, AuditEngagement.Status.CANCELLED])
            engagements = _apply_scope(engagements.select_related("organization_unit"), audit_view)
            for engagement in engagements:
                add_item(
                    source="audit_engagement",
                    source_id=engagement.id,
                    title=engagement.title,
                    subtitle=engagement.get_audit_type_display(),
                    status=engagement.status,
                    status_label=engagement.get_status_display(),
                    responsibility="lead_auditor",
                    due_date=engagement.end_date,
                    href=f"/audits/{engagement.id}",
                    organization_unit=_unit_name(engagement),
                    can_act=_scope_allows(audit_manage, engagement.organization_unit_id),
                )

            tester_workpapers = Workpaper.objects.filter(
                engagement__tenant=tenant,
                engagement__deleted_at__isnull=True,
                tester=user,
                status=Workpaper.Status.DRAFT,
                deleted_at__isnull=True,
            )
            tester_workpapers = _apply_scope(
                tester_workpapers.select_related("engagement__organization_unit", "engagement"),
                audit_view,
                "engagement__organization_unit_id",
            )
            for workpaper in tester_workpapers:
                engagement = workpaper.engagement
                add_item(
                    source="audit_workpaper",
                    source_id=workpaper.id,
                    title=workpaper.title,
                    subtitle=engagement.title,
                    status=workpaper.status,
                    status_label=workpaper.get_status_display(),
                    responsibility="tester",
                    due_date=engagement.end_date,
                    href=f"/audits/{engagement.id}",
                    organization_unit=_unit_name(engagement),
                    can_act=_scope_allows(audit_perform, engagement.organization_unit_id),
                )

        audit_review_visibility = _intersect_scopes(audit_view, audit_review)
        if audit_review_visibility is not None:
            review_workpapers = Workpaper.objects.filter(
                engagement__tenant=tenant,
                engagement__deleted_at__isnull=True,
                status=Workpaper.Status.READY,
                deleted_at__isnull=True,
            )
            review_workpapers = _apply_scope(
                review_workpapers.select_related("engagement__organization_unit", "engagement"),
                audit_review_visibility,
                "engagement__organization_unit_id",
            )
            for workpaper in review_workpapers:
                engagement = workpaper.engagement
                add_item(
                    source="audit_workpaper_review",
                    source_id=workpaper.id,
                    title=workpaper.title,
                    subtitle=engagement.title,
                    status=workpaper.status,
                    status_label=workpaper.get_status_display(),
                    responsibility="review_queue",
                    due_date=engagement.end_date,
                    href=f"/audits/{engagement.id}",
                    organization_unit=_unit_name(engagement),
                    is_review=True,
                    can_act=_scope_allows(audit_review, engagement.organization_unit_id),
                )

        attention_order = {"overdue": 0, "review": 1, "due_soon": 2, "normal": 3}
        items.sort(
            key=lambda item: (
                attention_order.get(item["attention"], 9),
                item["due_date"] or date.max,
                item["source"],
                item["title"].casefold(),
            )
        )
        source_counts = {}
        for item in items:
            source_counts[item["source"]] = source_counts.get(item["source"], 0) + 1

        return Response(
            {
                "schema_version": 1,
                "generated_at": timezone.now(),
                "due_soon_days": DUE_SOON_DAYS,
                "summary": {
                    "total": len(items),
                    "overdue": sum(1 for item in items if item["is_overdue"]),
                    "due_soon": sum(1 for item in items if item["is_due_soon"]),
                    "review": sum(1 for item in items if item["is_review"]),
                    "actionable": sum(1 for item in items if item["can_act"]),
                    "sources": source_counts,
                },
                "items": items,
            }
        )
