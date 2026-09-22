from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids, has_whole_tenant_permission, require_tenant_permission, require_whole_tenant_permission
from apps.tenancy.services import resolve_tenant_for_request
from .models import Control, ControlCategory, ControlImplementation, ControlRequirement
from .serializers import ControlCategorySerializer, ControlImplementationSerializer, ControlRequirementSerializer, ControlSerializer
from .services import require_local_control, visible_controls


class TenantMixin:
    def _tenant(self):
        if not hasattr(self, "_resolved_tenant"):
            self._resolved_tenant = resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self):
        ctx = super().get_serializer_context(); ctx["tenant"] = self._tenant(); return ctx


class ControlCategoryViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = ControlCategorySerializer
    def get_queryset(self):
        tenant=self._tenant(); require_tenant_permission(self.request.user, tenant, "control.view")
        return ControlCategory.objects.filter(deleted_at__isnull=True).filter(Q(tenant=tenant)|Q(tenant__isnull=True)).order_by("code")
    def perform_create(self, serializer):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "control.manage")
        obj=serializer.save(tenant=tenant); record_audit_event(self.request.user, tenant, "control_category.create", "control_category", obj.id, request=self.request)
    def perform_update(self, serializer):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "control.manage")
        if serializer.instance.tenant_id != tenant.id: raise PermissionDenied("Global categories are read-only.")
        obj=serializer.save(); record_audit_event(self.request.user, tenant, "control_category.update", "control_category", obj.id, request=self.request)
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "control.manage")
        if instance.tenant_id != tenant.id: raise PermissionDenied("Global categories are read-only.")
        if instance.children.filter(deleted_at__isnull=True).exists() or instance.controls.filter(deleted_at__isnull=True).exists(): raise ValidationError("Category is in use.")
        instance.deleted_at=timezone.now(); instance.save(update_fields=["deleted_at","updated_at"])


class ControlViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = ControlSerializer
    def get_queryset(self):
        tenant=self._tenant(); require_tenant_permission(self.request.user, tenant, "control.view")
        qs=visible_controls(tenant).select_related("category")
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(code__icontains=search)|Q(title__icontains=search)|Q(description__icontains=search))
        framework=self.request.query_params.get("framework")
        if framework: qs=qs.filter(requirement_mappings__requirement__framework_version__framework_id=framework).distinct()
        return qs.order_by("code")
    def perform_create(self, serializer):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "control.manage")
        obj=serializer.save(tenant=tenant, created_by=self.request.user); record_audit_event(self.request.user, tenant, "control.create", "control", obj.id, new_data={"code":obj.code,"title":obj.title}, object_repr=str(obj), request=self.request)
    def perform_update(self, serializer):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "control.manage"); require_local_control(serializer.instance, tenant)
        obj=serializer.save(); record_audit_event(self.request.user, tenant, "control.update", "control", obj.id, request=self.request)
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user, tenant, "control.manage"); require_local_control(instance, tenant)
        if instance.implementations.filter(deleted_at__isnull=True).exists(): raise ValidationError("A control with implementations cannot be archived.")
        instance.deleted_at=timezone.now(); instance.status=Control.Status.ARCHIVED; instance.save(update_fields=["deleted_at","status","updated_at"])
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        tenant=self._tenant(); require_whole_tenant_permission(request.user, tenant, "control.manage")
        source=self.get_object(); code=request.data.get("code")
        if not code: raise ValidationError({"code":"code is required"})
        if Control.objects.filter(tenant=tenant,code=code,deleted_at__isnull=True).exists(): raise ValidationError({"code":"Control code already exists."})
        clone=Control.objects.create(tenant=tenant,code=code,title=request.data.get("title") or source.title,description=source.description,objective=source.objective,category=source.category if source.category_id and source.category.tenant_id in {None,tenant.id} else None,control_type=source.control_type,nature=source.nature,frequency=source.frequency,automation_level=source.automation_level,status=Control.Status.DRAFT,metadata=source.metadata,created_by=request.user)
        for row in source.requirement_mappings.filter(deleted_at__isnull=True).filter(Q(tenant=tenant)|Q(tenant__isnull=True)):
            ControlRequirement.objects.get_or_create(tenant=tenant,control=clone,requirement=row.requirement,defaults={"coverage":row.coverage,"mapping_type":row.mapping_type,"rationale":row.rationale,"source":"duplicated","approved":False})
        return Response(self.get_serializer(clone).data, status=201)


class ControlRequirementViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class=ControlRequirementSerializer
    def get_queryset(self):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"control.view")
        qs=ControlRequirement.objects.filter(deleted_at__isnull=True).filter(Q(tenant=tenant)|Q(tenant__isnull=True)).select_related("control","requirement__framework_version__framework")
        if self.request.query_params.get("control"): qs=qs.filter(control_id=self.request.query_params["control"])
        return qs
    def perform_create(self,serializer):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user,tenant,"control.manage")
        obj=serializer.save(tenant=tenant,approved=False); record_audit_event(self.request.user,tenant,"control_requirement.create","control_requirement",obj.id,new_data={"control":str(obj.control_id),"requirement":str(obj.requirement_id),"source":obj.source,"approved":False},request=self.request)
    def perform_update(self,serializer):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user,tenant,"control.manage")
        if serializer.instance.tenant_id!=tenant.id: raise PermissionDenied("Global mappings are read-only.")
        obj=serializer.save(approved=False); record_audit_event(self.request.user,tenant,"control_requirement.update","control_requirement",obj.id,new_data={"approved":False,"source":obj.source},request=self.request)
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_whole_tenant_permission(self.request.user,tenant,"control.manage")
        if instance.tenant_id!=tenant.id: raise PermissionDenied("Global mappings are read-only.")
        instance.delete()
    @action(detail=True,methods=["post"])
    def approve(self,request,pk=None):
        tenant=self._tenant(); require_whole_tenant_permission(request.user,tenant,"control.manage")
        mapping=self.get_object()
        if mapping.tenant_id!=tenant.id: raise PermissionDenied("Global mappings are read-only.")
        mapping.approved=True; mapping.save(update_fields=["approved","updated_at"])
        record_audit_event(request.user,tenant,"control_requirement.approve","control_requirement",mapping.id,new_data={"approved":True,"control":str(mapping.control_id),"requirement":str(mapping.requirement_id),"source":mapping.source},request=request)
        return Response(self.get_serializer(mapping).data)


class ControlImplementationViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class=ControlImplementationSerializer
    def _perm(self): return "control.implementation.view" if self.action in {"list","retrieve"} else "control.implementation.manage"
    def get_queryset(self):
        tenant=self._tenant(); code=self._perm(); require_tenant_permission(self.request.user,tenant,code)
        allowed=accessible_organization_unit_ids(self.request.user,tenant,code)
        qs=ControlImplementation.objects.filter(tenant=tenant,deleted_at__isnull=True,organization_unit_id__in=allowed).select_related("control","organization_unit","owner","operator")
        if self.request.query_params.get("control"): qs=qs.filter(control_id=self.request.query_params["control"])
        return qs
    def perform_create(self,serializer):
        tenant=self._tenant(); unit=serializer.validated_data["organization_unit"]; require_tenant_permission(self.request.user,tenant,"control.implementation.manage",unit)
        obj=serializer.save(tenant=tenant); record_audit_event(self.request.user,tenant,"control_implementation.create","control_implementation",obj.id,new_data={"control":str(obj.control_id),"unit":str(obj.organization_unit_id)},request=self.request)
    def perform_update(self,serializer):
        tenant=self._tenant(); instance=serializer.instance; require_tenant_permission(self.request.user,tenant,"control.implementation.manage",instance.organization_unit)
        obj=serializer.save(); record_audit_event(self.request.user,tenant,"control_implementation.update","control_implementation",obj.id,request=self.request)
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"control.implementation.manage",instance.organization_unit)
        if instance.risk_links.filter(deleted_at__isnull=True).exists(): raise ValidationError("Control implementation is referenced by active risks.")
        instance.deleted_at=timezone.now(); instance.save(update_fields=["deleted_at","updated_at"])


from .models import ControlTest,ControlTestRun
from .serializers import ControlTestSerializer,ControlTestRunSerializer
class ControlTestViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=ControlTestSerializer
    def get_queryset(self):
        t=self._tenant();require_tenant_permission(self.request.user,t,'control.test.view');qs=ControlTest.objects.filter(control_implementation__tenant=t,deleted_at__isnull=True).select_related('control_implementation__organization_unit','control_implementation__control','owner')
        if has_whole_tenant_permission(self.request.user,t,'control.test.view'): return qs
        return qs.filter(control_implementation__organization_unit_id__in=accessible_organization_unit_ids(self.request.user,t,'control.test.view'))
    def perform_create(self,s):
        t=self._tenant();ci=s.validated_data['control_implementation'];require_tenant_permission(self.request.user,t,'control.test.manage',ci.organization_unit);s.save()
    def perform_update(self,s):
        t=self._tenant();require_tenant_permission(self.request.user,t,'control.test.manage',s.instance.control_implementation.organization_unit);s.save()
    @action(detail=True,methods=['post'])
    def run(self,request,pk=None):
        from django.utils import timezone as djtz
        test=self.get_object();t=self._tenant();require_tenant_permission(request.user,t,'control.test.execute',test.control_implementation.organization_unit);payload=dict(request.data);payload['control_test']=str(test.id);payload.setdefault('executed_at',djtz.now());ser=ControlTestRunSerializer(data=payload,context={'tenant':t});ser.is_valid(raise_exception=True);row=ser.save(executed_by=request.user);test.control_implementation.effectiveness={'pass':'effective','partial':'partial','fail':'ineffective'}.get(row.result,test.control_implementation.effectiveness);test.control_implementation.save(update_fields=['effectiveness','updated_at']);record_audit_event(request.user,t,'control_test.run','control_test_run',row.id,new_data={'result':row.result},request=request);return Response(ControlTestRunSerializer(row,context={'tenant':t}).data,status=201)
class ControlTestRunViewSet(TenantMixin,viewsets.ReadOnlyModelViewSet):
    serializer_class=ControlTestRunSerializer
    def get_queryset(self):
        t=self._tenant();require_tenant_permission(self.request.user,t,'control.test.view');qs=ControlTestRun.objects.filter(control_test__control_implementation__tenant=t,deleted_at__isnull=True).select_related('control_test__control_implementation__organization_unit','executed_by');
        if has_whole_tenant_permission(self.request.user,t,'control.test.view'): return qs.order_by('-executed_at')
        return qs.filter(control_test__control_implementation__organization_unit_id__in=accessible_organization_unit_ids(self.request.user,t,'control.test.view')).order_by('-executed_at')
