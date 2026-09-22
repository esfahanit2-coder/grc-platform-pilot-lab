from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids, has_whole_tenant_permission, require_tenant_permission, require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .models import Assessment, AssessmentItem
from .serializers import AssessmentItemSerializer, AssessmentSerializer
from .services import create_assessment, recalculate_assessment


class TenantMixin:
    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self):
        ctx = super().get_serializer_context(); ctx["tenant"] = self._tenant(); return ctx


class AssessmentViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer

    def _perm(self):
        return "assessment.view" if self.action in {"list", "retrieve", "summary"} else "assessment.manage"

    def get_queryset(self):
        tenant = self._tenant(); code = self._perm(); require_tenant_permission(self.request.user, tenant, code)
        allowed = accessible_organization_unit_ids(self.request.user, tenant, code); whole = has_whole_tenant_permission(self.request.user, tenant, code)
        qs = Assessment.objects.filter(tenant=tenant, deleted_at__isnull=True).select_related("framework_version__framework", "organization_unit", "owner")
        if not whole:
            qs = qs.filter(organization_unit_id__in=allowed)
        if self.request.query_params.get("framework_version"):
            qs = qs.filter(framework_version_id=self.request.query_params["framework_version"])
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(framework_version__framework__name__icontains=search))
        return qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        tenant = self._tenant(); serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        unit = serializer.validated_data.get("organization_unit")
        require_tenant_permission(request.user, tenant, "assessment.manage", unit) if unit else require_whole_tenant_permission(request.user, tenant, "assessment.manage")
        data = serializer.validated_data
        obj = create_assessment(
            tenant=tenant,
            framework_version=data["framework_version"], title=data["title"], assessment_type=data.get("assessment_type", Assessment.AssessmentType.COMPLIANCE),
            owner=data["owner"], organization_unit=unit, start_date=data.get("start_date"), due_date=data.get("due_date"), metadata=data.get("metadata", {}),
        )
        record_audit_event(request.user, tenant, "assessment.create", "assessment", obj.id, new_data={"title": obj.title, "framework_version": str(obj.framework_version_id)}, request=request)
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        tenant = self._tenant(); obj = serializer.instance
        require_tenant_permission(self.request.user, tenant, "assessment.manage", obj.organization_unit) if obj.organization_unit else require_whole_tenant_permission(self.request.user, tenant, "assessment.manage")
        updated = serializer.save(); recalculate_assessment(updated)
        record_audit_event(self.request.user, tenant, "assessment.update", "assessment", updated.id, request=self.request)

    def perform_destroy(self, instance):
        tenant = self._tenant(); require_tenant_permission(self.request.user, tenant, "assessment.manage", instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user, tenant, "assessment.manage")
        instance.deleted_at = timezone.now(); instance.status = Assessment.Status.CANCELLED; instance.save(update_fields=["deleted_at", "status", "updated_at"])

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        assessment = self.get_object(); recalculate_assessment(assessment)
        counts = {key: assessment.items.filter(deleted_at__isnull=True, status=key).count() for key, _ in AssessmentItem.Status.choices}
        no_evidence = 0
        from apps.evidence.models import EvidenceLink
        item_ids = list(assessment.items.filter(deleted_at__isnull=True).values_list("id", flat=True))
        linked_ids = set(EvidenceLink.objects.filter(tenant=assessment.tenant, object_type="assessment_item", object_id__in=item_ids, deleted_at__isnull=True).values_list("object_id", flat=True))
        no_evidence = sum(1 for item_id in item_ids if item_id not in linked_ids)
        return Response({"id": str(assessment.id), "progress_percent": str(assessment.progress_percent), "overall_score": str(assessment.overall_score) if assessment.overall_score is not None else None, "status_counts": counts, "items_count": len(item_ids), "without_evidence": no_evidence})

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        assessment = self.get_object(); tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "assessment.review", assessment.organization_unit) if assessment.organization_unit else require_whole_tenant_permission(request.user, tenant, "assessment.review")
        if assessment.items.filter(deleted_at__isnull=True, status=AssessmentItem.Status.NOT_ASSESSED).exists():
            raise ValidationError({"items": "Assessment contains unassessed requirements."})
        recalculate_assessment(assessment); assessment.status = Assessment.Status.COMPLETED; assessment.save(update_fields=["status", "updated_at"])
        record_audit_event(request.user, tenant, "assessment.complete", "assessment", assessment.id, request=request)
        return Response(self.get_serializer(assessment).data)


class AssessmentItemViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = AssessmentItemSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        tenant = self._tenant(); code = "assessment.perform" if self.action in {"partial_update", "update"} else "assessment.view"; require_tenant_permission(self.request.user, tenant, code)
        allowed = accessible_organization_unit_ids(self.request.user, tenant, code); whole = has_whole_tenant_permission(self.request.user, tenant, code)
        qs = AssessmentItem.objects.filter(assessment__tenant=tenant, assessment__deleted_at__isnull=True, deleted_at__isnull=True).select_related("assessment__organization_unit", "requirement", "assigned_to", "reviewed_by")
        if not whole:
            qs = qs.filter(assessment__organization_unit_id__in=allowed)
        if self.request.query_params.get("assessment"):
            qs = qs.filter(assessment_id=self.request.query_params["assessment"])
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("assigned_to_me") in {"1", "true"}:
            qs = qs.filter(assigned_to=self.request.user)
        return qs.order_by("requirement__sort_order", "requirement_code_snapshot")

    def perform_update(self, serializer):
        tenant = self._tenant(); item = serializer.instance; assessment = item.assessment
        require_tenant_permission(self.request.user, tenant, "assessment.perform", assessment.organization_unit) if assessment.organization_unit else require_whole_tenant_permission(self.request.user, tenant, "assessment.perform")
        obj = serializer.save(); recalculate_assessment(assessment)
        record_audit_event(self.request.user, tenant, "assessment_item.update", "assessment_item", obj.id, new_data={"status": obj.status, "score": str(obj.score) if obj.score is not None else None}, request=self.request)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        item = self.get_object(); assessment = item.assessment; tenant = self._tenant()
        require_tenant_permission(request.user, tenant, "assessment.review", assessment.organization_unit) if assessment.organization_unit else require_whole_tenant_permission(request.user, tenant, "assessment.review")
        item.reviewer_comment = str(request.data.get("reviewer_comment") or "")
        item.reviewed_by = request.user
        item.save(update_fields=["reviewer_comment", "reviewed_by", "updated_at"])
        record_audit_event(request.user, tenant, "assessment_item.review", "assessment_item", item.id, request=request)
        return Response(self.get_serializer(item).data)
