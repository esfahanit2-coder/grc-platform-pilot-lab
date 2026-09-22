from django.db.models import Avg, Count, OuterRef, Q, Subquery
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.actions.models import Action
from apps.assessments.models import Assessment
from apps.audit.services import record_audit_event
from apps.controls.models import ControlImplementation
from apps.documents.models import ReportTemplate
from apps.findings.models import Finding
from apps.identity.services import (
    accessible_organization_unit_ids,
    has_whole_tenant_permission,
    require_tenant_permission,
    require_whole_tenant_permission,
)
from apps.internal_audits.models import AuditEngagement
from apps.risks.models import Risk, RiskEvaluation
from apps.tenancy.services import resolve_tenant_for_request

from .template_engine import render_html, render_pdf
from .formal_reports import (
    BUILDERS,
    REPORT_CATALOG,
    export_csv,
    export_docx,
    export_xlsx,
    normalized_filters,
    public_filters,
    table_html,
)


def _owner_display(user):
    full_name = user.get_full_name().strip()
    return full_name or user.get_username()


def _float_or_none(value):
    return None if value is None else float(value)


def _scoped_filter(tenant, whole_tenant, allowed_units):
    query = Q(tenant=tenant, deleted_at__isnull=True)
    if not whole_tenant:
        query &= Q(organization_unit_id__in=allowed_units)
    return query


class ManagementDashboardView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_tenant_permission(request.user, tenant, "report.view")
        whole_tenant = has_whole_tenant_permission(request.user, tenant, "report.view")
        allowed_units = accessible_organization_unit_ids(request.user, tenant, "report.view")

        scoped = _scoped_filter(tenant, whole_tenant, allowed_units)
        risks = Risk.objects.filter(scoped)
        findings = Finding.objects.filter(scoped)
        actions = Action.objects.filter(scoped)
        assessments = Assessment.objects.filter(scoped)
        controls = ControlImplementation.objects.filter(scoped)
        audit_engagements = AuditEngagement.objects.filter(scoped)

        latest_residual = RiskEvaluation.objects.filter(
            risk_id=OuterRef("pk"),
            evaluation_type=RiskEvaluation.EvaluationType.RESIDUAL,
            deleted_at__isnull=True,
        ).order_by("-evaluated_at", "-created_at")
        active_risks = risks.exclude(status__in=[Risk.Status.CLOSED, Risk.Status.ARCHIVED]).annotate(
            latest_residual_score=Subquery(latest_residual.values("score")[:1]),
            latest_residual_level=Subquery(latest_residual.values("level")[:1]),
            latest_residual_likelihood=Subquery(latest_residual.values("likelihood")[:1]),
            latest_residual_impact=Subquery(latest_residual.values("impact")[:1]),
            latest_residual_evaluated_at=Subquery(latest_residual.values("evaluated_at")[:1]),
        )

        latest_high = active_risks.filter(latest_residual_level__in=["high", "critical"]).count()
        overdue = actions.exclude(status__in=[Action.Status.DONE, Action.Status.CANCELLED]).filter(
            due_date__lt=timezone.localdate()
        ).count()

        score_values = list(
            assessments.exclude(overall_score__isnull=True).values_list("overall_score", flat=True)
        )
        compliance_score = (
            round(sum(float(value) for value in score_values) / len(score_values), 2)
            if score_values
            else None
        )

        effectiveness_counts = {
            row["effectiveness"]: row["count"]
            for row in controls.values("effectiveness").annotate(count=Count("id"))
        }
        assessed_controls = sum(
            count
            for effectiveness, count in effectiveness_counts.items()
            if effectiveness != ControlImplementation.Effectiveness.NOT_ASSESSED
        )
        effective_controls_percent = (
            round(
                effectiveness_counts.get(ControlImplementation.Effectiveness.EFFECTIVE, 0)
                * 100
                / assessed_controls,
                1,
            )
            if assessed_controls
            else None
        )

        framework_summaries = []
        framework_rows = (
            assessments.exclude(status=Assessment.Status.CANCELLED)
            .values(
                "framework_version_id",
                "framework_version__framework__code",
                "framework_version__framework__name",
                "framework_version__version_code",
            )
            .annotate(
                assessment_count=Count("id"),
                average_score=Avg("overall_score"),
                average_progress=Avg("progress_percent"),
                completed_count=Count("id", filter=Q(status=Assessment.Status.COMPLETED)),
                in_progress_count=Count(
                    "id",
                    filter=Q(status__in=[Assessment.Status.IN_PROGRESS, Assessment.Status.IN_REVIEW]),
                ),
                draft_count=Count("id", filter=Q(status=Assessment.Status.DRAFT)),
            )
            .order_by("framework_version__framework__name", "framework_version__version_code")[:8]
        )
        for row in framework_rows:
            framework_summaries.append(
                {
                    "framework_version_id": row["framework_version_id"],
                    "framework_code": row["framework_version__framework__code"],
                    "framework_name": row["framework_version__framework__name"],
                    "version_code": row["framework_version__version_code"],
                    "assessment_count": row["assessment_count"],
                    "average_score": _float_or_none(row["average_score"]),
                    "average_progress": _float_or_none(row["average_progress"]),
                    "completed_count": row["completed_count"],
                    "in_progress_count": row["in_progress_count"],
                    "draft_count": row["draft_count"],
                }
            )

        severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        heatmap = {}
        heatmap_rows = (
            active_risks.exclude(latest_residual_score__isnull=True)
            .values(
                "latest_residual_likelihood",
                "latest_residual_impact",
                "latest_residual_level",
            )
            .annotate(count=Count("id"))
        )
        for row in heatmap_rows:
            likelihood = _float_or_none(row["latest_residual_likelihood"])
            impact = _float_or_none(row["latest_residual_impact"])
            if likelihood is None or impact is None:
                continue
            key = (likelihood, impact)
            cell = heatmap.setdefault(
                key,
                {
                    "likelihood": likelihood,
                    "impact": impact,
                    "count": 0,
                    "max_level": row["latest_residual_level"] or "",
                },
            )
            cell["count"] += row["count"]
            candidate = row["latest_residual_level"] or ""
            if severity_rank.get(candidate, 0) > severity_rank.get(cell["max_level"], 0):
                cell["max_level"] = candidate

        top_risks = []
        for risk in (
            active_risks.exclude(latest_residual_score__isnull=True)
            .select_related("owner")
            .order_by("-latest_residual_score", "code")[:5]
        ):
            top_risks.append(
                {
                    "id": risk.id,
                    "code": risk.code,
                    "title": risk.title,
                    "status": risk.status,
                    "owner": _owner_display(risk.owner),
                    "score": _float_or_none(risk.latest_residual_score),
                    "level": risk.latest_residual_level,
                    "likelihood": _float_or_none(risk.latest_residual_likelihood),
                    "impact": _float_or_none(risk.latest_residual_impact),
                    "evaluated_at": risk.latest_residual_evaluated_at,
                }
            )

        active_actions = actions.exclude(status__in=[Action.Status.DONE, Action.Status.CANCELLED])
        attention_actions = []
        today = timezone.localdate()
        for action in active_actions.select_related("owner").order_by("due_date", "-priority", "title")[:6]:
            attention_actions.append(
                {
                    "id": action.id,
                    "title": action.title,
                    "owner": _owner_display(action.owner),
                    "priority": action.priority,
                    "status": action.status,
                    "progress": action.progress,
                    "source_type": action.source_type,
                    "source_id": action.source_id,
                    "due_date": action.due_date,
                    "is_overdue": bool(action.due_date and action.due_date < today),
                }
            )

        upcoming_deadlines = []
        for assessment in (
            assessments.exclude(status__in=[Assessment.Status.COMPLETED, Assessment.Status.CANCELLED])
            .filter(due_date__gte=today)
            .select_related("framework_version__framework")
            .order_by("due_date")[:8]
        ):
            upcoming_deadlines.append(
                {
                    "type": "assessment",
                    "date": assessment.due_date,
                    "title": assessment.title,
                    "subtitle": assessment.framework_version.framework.name,
                    "href": f"/assessments/{assessment.id}",
                }
            )
        for action in active_actions.filter(due_date__gte=today).order_by("due_date")[:8]:
            upcoming_deadlines.append(
                {
                    "type": "action",
                    "date": action.due_date,
                    "title": action.title,
                    "subtitle": action.get_priority_display(),
                    "href": "/actions",
                }
            )
        for risk in (
            risks.exclude(status__in=[Risk.Status.CLOSED, Risk.Status.ARCHIVED])
            .filter(review_date__gte=today)
            .order_by("review_date")[:8]
        ):
            upcoming_deadlines.append(
                {
                    "type": "risk_review",
                    "date": risk.review_date,
                    "title": risk.title,
                    "subtitle": risk.code,
                    "href": f"/risks/{risk.id}",
                }
            )
        for engagement in (
            audit_engagements.exclude(
                status__in=[AuditEngagement.Status.COMPLETED, AuditEngagement.Status.CANCELLED]
            )
            .filter(start_date__gte=today)
            .order_by("start_date")[:8]
        ):
            upcoming_deadlines.append(
                {
                    "type": "audit",
                    "date": engagement.start_date,
                    "title": engagement.title,
                    "subtitle": engagement.get_audit_type_display(),
                    "href": f"/audits/{engagement.id}",
                }
            )
        upcoming_deadlines.sort(key=lambda item: (item["date"], item["type"], item["title"]))
        upcoming_deadlines = upcoming_deadlines[:8]

        top_findings = list(
            findings.exclude(status__in=["closed", "accepted"])
            .order_by("due_date", "-created_at")
            .values("id", "title", "severity", "due_date")[:10]
        )

        return Response(
            {
                "dashboard_schema_version": 2,
                "compliance_score": compliance_score,
                "high_critical_residual_risks": latest_high,
                "open_findings": findings.exclude(status__in=["closed", "accepted"]).count(),
                "overdue_actions": overdue,
                "control_effectiveness": effectiveness_counts,
                "effective_controls_percent": effective_controls_percent,
                "assessments_due": assessments.exclude(
                    status__in=[Assessment.Status.COMPLETED, Assessment.Status.CANCELLED]
                )
                .filter(due_date__isnull=False)
                .count(),
                "top_findings": top_findings,
                "framework_summaries": framework_summaries,
                "risk_heatmap": sorted(
                    heatmap.values(), key=lambda item: (item["likelihood"], item["impact"])
                ),
                "top_risks": top_risks,
                "attention_actions": attention_actions,
                "upcoming_deadlines": upcoming_deadlines,
            }
        )


class TemplateRenderView(APIView):
    def post(self, request):
        tenant = resolve_tenant_for_request(request)
        require_whole_tenant_permission(request.user, tenant, "report.generate")
        template = (
            ReportTemplate.objects.filter(id=request.data.get("template_id"), deleted_at__isnull=True)
            .filter(Q(tenant=tenant) | Q(tenant__isnull=True))
            .first()
        )
        if not template:
            raise ValidationError("Report template not found.")
        html_template = (template.configuration or {}).get("html_template")
        if not html_template:
            raise ValidationError("Template configuration has no html_template.")
        context = request.data.get("context") or {}
        fmt = str(request.data.get("format", "html")).lower()
        if fmt not in {"html", "pdf"}:
            raise ValidationError({"format": "Only html and pdf report formats are supported."})
        try:
            if fmt == "pdf":
                payload, _ = render_pdf(
                    html_template,
                    context,
                    (template.configuration or {}).get("css", ""),
                )
                record_audit_event(
                    request.user,
                    tenant,
                    "report.export",
                    "report_template",
                    template.id,
                    metadata={"format": "pdf"},
                    request=request,
                )
                response = HttpResponse(payload, content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="report-{template.id}.pdf"'
                return response
            payload = render_html(html_template, context)
            record_audit_event(
                request.user,
                tenant,
                "report.export",
                "report_template",
                template.id,
                metadata={"format": "html"},
                request=request,
            )
            return HttpResponse(payload, content_type="text/html; charset=utf-8")
        except Exception as exc:
            record_audit_event(
                request.user,
                tenant,
                "report.export",
                "report_template",
                template.id,
                outcome="failure",
                metadata={"format": fmt, "error_type": type(exc).__name__},
                request=request,
            )
            raise ValidationError({"template": f"Render failed: {exc}"}) from exc



class ReportCatalogView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_tenant_permission(request.user, tenant, "report.view")
        return Response({"reports": REPORT_CATALOG})


class FormalReportPreviewView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_tenant_permission(request.user, tenant, "report.view")
        report_type = str(request.query_params.get("type") or "").lower()
        if report_type not in REPORT_CATALOG:
            raise ValidationError({"type": "Unsupported report type."})
        filters = normalized_filters(request, tenant, "report.view")
        if report_type == "executive":
            dashboard = ManagementDashboardView().get(request).data
            report = {
                "title": "Executive Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    ["Compliance score", dashboard.get("compliance_score")],
                    ["High/Critical residual risks", dashboard.get("high_critical_residual_risks")],
                    ["Open findings", dashboard.get("open_findings")],
                    ["Overdue actions", dashboard.get("overdue_actions")],
                    ["Effective controls %", dashboard.get("effective_controls_percent")],
                    ["Assessments due", dashboard.get("assessments_due")],
                ],
                "summary": {"dashboard_schema_version": dashboard.get("dashboard_schema_version")},
            }
        else:
            report = BUILDERS[report_type](tenant, filters)
        return Response({
            "type": report_type,
            "filters": public_filters(filters),
            **report,
        })


class FormalReportExportView(APIView):
    def get(self, request):
        tenant = resolve_tenant_for_request(request)
        require_tenant_permission(request.user, tenant, "report.generate")
        report_type = str(request.query_params.get("type") or "").lower()
        fmt = str(request.query_params.get("format") or "pdf").lower()
        if report_type not in REPORT_CATALOG:
            raise ValidationError({"type": "Unsupported report type."})
        if fmt not in REPORT_CATALOG[report_type]["formats"]:
            raise ValidationError({"format": "Unsupported format for this report type."})
        filters = normalized_filters(request, tenant, "report.generate")
        if report_type == "executive":
            dashboard = ManagementDashboardView().get(request).data
            report = {
                "title": "Executive Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    ["Compliance score", dashboard.get("compliance_score")],
                    ["High/Critical residual risks", dashboard.get("high_critical_residual_risks")],
                    ["Open findings", dashboard.get("open_findings")],
                    ["Overdue actions", dashboard.get("overdue_actions")],
                    ["Effective controls %", dashboard.get("effective_controls_percent")],
                    ["Assessments due", dashboard.get("assessments_due")],
                ],
                "summary": {},
            }
        else:
            report = BUILDERS[report_type](tenant, filters)

        if fmt == "csv":
            payload, content_type = export_csv(report), "text/csv; charset=utf-8"
        elif fmt == "xlsx":
            payload, content_type = export_xlsx(report), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif fmt == "docx":
            payload, content_type = export_docx(report), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            payload, _ = render_pdf(table_html(report), {})
            content_type = "application/pdf"

        record_audit_event(
            request.user,
            tenant,
            "report.export",
            "formal_report",
            tenant.id,
            metadata={
                "report_type": report_type,
                "format": fmt,
                "filters": public_filters(filters),
                "row_count": len(report["rows"]),
            },
            request=request,
        )
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{report_type}-report.{fmt}"'
        return response
