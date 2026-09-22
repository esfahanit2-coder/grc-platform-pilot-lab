import json
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.audit.services import record_audit_event
from apps.controls.models import Control, ControlRequirement
from apps.frameworks.models import FrameworkVersion, Requirement
from apps.frameworks.services import visible_frameworks
from apps.identity.services import accessible_organization_unit_ids, has_whole_tenant_permission, require_tenant_permission, require_whole_tenant_permission
from apps.risks.models import Risk
from apps.tenancy.services import resolve_tenant_for_request
from .models import AIProviderConfig, AIInteraction, AISuggestion, KnowledgeChunk
from .serializers import AIProviderConfigSerializer, AIInteractionSerializer, AISuggestionSerializer, KnowledgeChunkSerializer
from .services import create_suggestion, embed_knowledge_chunk, rag_answer, review_suggestion, run_ai, select_provider, upsert_knowledge_chunk


class TenantMixin:
    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant


class AIProviderViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = AIProviderConfigSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    def get_queryset(self):
        tenant = self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "ai.configure")
        return AIProviderConfig.objects.filter(tenant=tenant, deleted_at__isnull=True).order_by("name")
    def perform_create(self, serializer):
        tenant = self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "ai.configure")
        if serializer.validated_data.get("is_default"):
            AIProviderConfig.objects.filter(tenant=tenant).update(is_default=False)
        obj = serializer.save(tenant=tenant)
        record_audit_event(
            self.request.user, tenant, "ai.provider.create", "ai_provider_config", obj.id,
            metadata={
                "provider_type": obj.provider_type,
                "is_default": obj.is_default,
                "allow_confidential": obj.allow_confidential,
            },
            request=self.request,
        )
    def perform_update(self, serializer):
        tenant = self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "ai.configure")
        if serializer.validated_data.get("is_default"):
            AIProviderConfig.objects.filter(tenant=tenant).exclude(id=serializer.instance.id).update(is_default=False)
        obj = serializer.save()
        record_audit_event(
            self.request.user, tenant, "ai.provider.update", "ai_provider_config", obj.id,
            metadata={
                "provider_type": obj.provider_type,
                "is_default": obj.is_default,
                "allow_confidential": obj.allow_confidential,
            },
            request=self.request,
        )
    def perform_destroy(self, instance):
        tenant = self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "ai.configure")
        instance.deleted_at = __import__('django.utils.timezone', fromlist=['now']).now(); instance.is_active = False; instance.save(update_fields=["deleted_at","is_active","updated_at"])
        record_audit_event(
            self.request.user, tenant, "ai.provider.delete", "ai_provider_config", instance.id,
            metadata={"provider_type": instance.provider_type},
            request=self.request,
        )


class AIInteractionViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AIInteractionSerializer
    def get_queryset(self):
        tenant=self._tenant(); require_tenant_permission(self.request.user, tenant, "ai.use")
        qs=AIInteraction.objects.filter(tenant=tenant)
        if not require_is_auditor(self.request.user, tenant): qs=qs.filter(user=self.request.user)
        return qs.order_by("-created_at")


def require_is_auditor(user, tenant):
    from apps.identity.services import has_whole_tenant_permission
    return has_whole_tenant_permission(user, tenant, "ai.audit")


class AISuggestionViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class=AISuggestionSerializer
    def get_queryset(self):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"ai.use")
        qs=AISuggestion.objects.filter(tenant=tenant).select_related("interaction","reviewed_by")
        if not require_is_auditor(self.request.user,tenant): qs=qs.filter(interaction__user=self.request.user)
        status_filter=self.request.query_params.get("status")
        if status_filter: qs=qs.filter(status=status_filter)
        return qs.order_by("-created_at")
    @action(detail=True,methods=["post"])
    def review(self,request,pk=None):
        suggestion=self.get_object(); requested=str(request.data.get("status","")).strip(); modified=request.data.get("proposed_value")
        review_suggestion(suggestion,user=request.user,status=requested,comment=request.data.get("comment",""),modified_value=modified,request=request)
        return Response(self.get_serializer(suggestion).data)


class KnowledgeChunkViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class=KnowledgeChunkSerializer
    http_method_names=["get","post","delete","head","options"]
    def get_queryset(self):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"ai.knowledge.view")
        qs=KnowledgeChunk.objects.filter(tenant=tenant,deleted_at__isnull=True)
        if not has_whole_tenant_permission(self.request.user,tenant,"ai.knowledge.view"):
            allowed=accessible_organization_unit_ids(self.request.user,tenant,"ai.knowledge.view")
            qs=qs.filter(Q(organization_unit_id__in=allowed)|Q(organization_unit__isnull=True,classification="public"))
        return qs.order_by("-updated_at")
    def create(self,request,*args,**kwargs):
        tenant=self._tenant(); require_tenant_permission(request.user,tenant,"ai.knowledge.manage")
        serializer=self.get_serializer(data=request.data);serializer.is_valid(raise_exception=True)
        unit=serializer.validated_data.get("organization_unit")
        if unit and unit.tenant_id!=tenant.id: raise ValidationError("Organization unit belongs to another tenant.")
        if unit: require_tenant_permission(request.user,tenant,"ai.knowledge.manage",unit)
        else: require_whole_tenant_permission(request.user,tenant,"ai.knowledge.manage")
        row=upsert_knowledge_chunk(tenant=tenant,organization_unit=unit,source_type=serializer.validated_data["source_type"],source_id=serializer.validated_data.get("source_id"),title=serializer.validated_data.get("title",""),content=serializer.validated_data["content"],classification=serializer.validated_data.get("classification","internal"),metadata=serializer.validated_data.get("metadata",{}))
        record_audit_event(
            request.user, tenant, "ai.knowledge.upsert", "knowledge_chunk", row.id,
            metadata={
                "source_type": row.source_type,
                "classification": row.classification,
                "organization_unit_id": str(row.organization_unit_id) if row.organization_unit_id else None,
            },
            request=request,
        )
        return Response(self.get_serializer(row).data,status=status.HTTP_201_CREATED)
    def perform_destroy(self,instance):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"ai.knowledge.manage",instance.organization_unit) if instance.organization_unit else require_whole_tenant_permission(self.request.user,tenant,"ai.knowledge.manage")
        from django.utils import timezone
        instance.deleted_at=timezone.now();instance.save(update_fields=["deleted_at","updated_at"])
        record_audit_event(
            self.request.user, tenant, "ai.knowledge.delete", "knowledge_chunk", instance.id,
            metadata={
                "source_type": instance.source_type,
                "classification": instance.classification,
                "organization_unit_id": str(instance.organization_unit_id) if instance.organization_unit_id else None,
            },
            request=self.request,
        )
    @action(detail=True,methods=["post"])
    def embed(self,request,pk=None):
        tenant=self._tenant(); chunk=self.get_object()
        require_tenant_permission(request.user,tenant,"ai.knowledge.manage",chunk.organization_unit) if chunk.organization_unit else require_whole_tenant_permission(request.user,tenant,"ai.knowledge.manage")
        provider=select_provider(tenant,request.data.get("provider_id"))
        embed_knowledge_chunk(chunk,provider_cfg=provider)
        record_audit_event(
            request.user, tenant, "ai.knowledge.embed", "knowledge_chunk", chunk.id,
            metadata={
                "provider_type": provider.provider_type,
                "embedding_model": chunk.embedding_model,
                "embedding_dimensions": chunk.embedding_dimensions,
            },
            request=request,
        )
        return Response(self.get_serializer(chunk).data)


class AIAssistantViewSet(TenantMixin, viewsets.ViewSet):
    def _require(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"ai.use");return tenant
    @action(detail=False,methods=["post"],url_path="risk")
    def risk_assistant(self,request):
        tenant=self._require();risk=None
        if request.data.get("risk_id"):
            risk=Risk.objects.filter(tenant=tenant,id=request.data["risk_id"],deleted_at__isnull=True).first()
            if not risk: raise ValidationError("Risk not found.")
            require_tenant_permission(request.user,tenant,"risk.view",risk.organization_unit) if risk.organization_unit else require_whole_tenant_permission(request.user,tenant,"risk.view")
        text=request.data.get("text") or (f"Risk: {risk.title}\nScenario: {risk.scenario}\nCause: {risk.cause}\nConsequence: {risk.consequence}" if risk else "")
        interaction,answer=run_ai(tenant=tenant,user=request.user,capability="risk_assistant",prompt=f"Analyze this risk and return concise proposed causes, impacts, controls and treatments. Do not make final decisions.\n\n{text}",system_prompt="You are a senior GRC risk analyst. Suggestions require human approval.",provider_id=request.data.get("provider_id"),classification=request.data.get("classification","internal"),context_manifest={"risk_id":str(risk.id) if risk else None},request=request)
        suggestion=create_suggestion(interaction=interaction,suggestion_type="risk_analysis",proposed_value={"text":answer},object_type="risk" if risk else "",object_id=risk.id if risk else None)
        return Response({"interaction":str(interaction.id),"suggestion":AISuggestionSerializer(suggestion).data})
    @action(detail=False,methods=["post"],url_path="control-mapping")
    def control_mapping(self,request):
        tenant=self._require()
        require_tenant_permission(request.user,tenant,"control.view")
        require_tenant_permission(request.user,tenant,"framework.view")
        control=Control.objects.filter(Q(tenant=tenant)|Q(tenant__isnull=True),id=request.data.get("control_id"),deleted_at__isnull=True).first()
        if not control: raise ValidationError("Control not found.")
        ids=request.data.get("requirement_ids") or []
        requirements=list(
            Requirement.objects.filter(
                id__in=ids,
                deleted_at__isnull=True,
                framework_version__deleted_at__isnull=True,
                framework_version__framework__in=visible_frameworks(tenant),
            )
            .filter(
                Q(framework_version__framework__tenant=tenant)
                | Q(
                    framework_version__framework__tenant__isnull=True,
                    framework_version__status=FrameworkVersion.Status.ACTIVE,
                )
            )
            .select_related("framework_version__framework")[:100]
        )
        req_text="\n".join(f"- {r.id}: {r.code} {r.title} — {r.body[:800]}" for r in requirements)
        prompt=f"Control: {control.code} {control.title}\n{control.description}\n\nCandidate requirements:\n{req_text}\n\nSuggest mappings with rationale and confidence."
        interaction,answer=run_ai(tenant=tenant,user=request.user,capability="control_mapping",prompt=prompt,system_prompt="You map GRC controls to requirements. Return advisory mappings only; never claim approval.",provider_id=request.data.get("provider_id"),classification=request.data.get("classification","internal"),context_manifest={"control_id":str(control.id),"requirement_ids":[str(r.id) for r in requirements]},request=request)
        suggestion=create_suggestion(interaction=interaction,suggestion_type="control_mapping",proposed_value={"text":answer},object_type="control",object_id=control.id)
        return Response({"interaction":str(interaction.id),"suggestion":AISuggestionSerializer(suggestion).data})
    @action(detail=False,methods=["post"],url_path="document-draft")
    def document_draft(self,request):
        tenant=self._require();title=str(request.data.get("title","")).strip();purpose=str(request.data.get("purpose","")).strip()
        if not title: raise ValidationError({"title":"Required."})
        interaction,answer=run_ai(tenant=tenant,user=request.user,capability="document_draft",prompt=f"Draft title: {title}\nPurpose/context: {purpose}\nCreate a professional draft with placeholders where evidence is unavailable.",system_prompt="You draft controlled GRC documents. Never fabricate organization facts; clearly mark placeholders and assumptions.",provider_id=request.data.get("provider_id"),classification=request.data.get("classification","internal"),context_manifest={},request=request)
        suggestion=create_suggestion(interaction=interaction,suggestion_type="document_draft",proposed_value={"title":title,"content":answer})
        return Response({"interaction":str(interaction.id),"suggestion":AISuggestionSerializer(suggestion).data})
    @action(detail=False,methods=["post"],url_path="rag")
    def rag(self,request):
        tenant=self._require();query=str(request.data.get("query","")).strip()
        if not query: raise ValidationError({"query":"Required."})
        interaction,answer,chunks=rag_answer(tenant=tenant,user=request.user,query=query,provider_id=request.data.get("provider_id"),classification=request.data.get("classification","internal"),request=request)
        return Response({"interaction":str(interaction.id),"answer":answer,"sources":[{"id":str(c.id),"title":c.title,"source_type":c.source_type,"source_id":str(c.source_id) if c.source_id else None} for c in chunks]})
