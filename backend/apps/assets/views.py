from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids, require_tenant_permission
from apps.tenancy.models import TenantMembership
from apps.tenancy.services import resolve_tenant_for_request
from .models import Asset, AssetDependency
from .serializers import AssetDependencySerializer, AssetSerializer

class TenantMixin:
    def _tenant(self):
        if not hasattr(self,"_resolved_tenant"): self._resolved_tenant=resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self): ctx=super().get_serializer_context();ctx["tenant"]=self._tenant();return ctx

class AssetViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=AssetSerializer
    def _perm(self): return "asset.view" if self.action in {"list","retrieve"} else "asset.manage"
    def get_queryset(self):
        tenant=self._tenant();code=self._perm();require_tenant_permission(self.request.user,tenant,code);allowed=accessible_organization_unit_ids(self.request.user,tenant,code)
        qs=Asset.objects.filter(tenant=tenant,deleted_at__isnull=True,organization_unit_id__in=allowed).select_related("organization_unit","owner","custodian")
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(code__icontains=search)|Q(title__icontains=search)|Q(description__icontains=search))
        if self.request.query_params.get("asset_type"): qs=qs.filter(asset_type=self.request.query_params["asset_type"])
        if self.request.query_params.get("status"): qs=qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("organization_unit"): qs=qs.filter(organization_unit_id=self.request.query_params["organization_unit"])
        return qs.order_by("code")
    @action(detail=False, methods=["get"], url_path="selector-options")
    def selector_options(self, request):
        tenant=self._tenant()
        require_tenant_permission(request.user,tenant,"asset.manage")
        allowed=accessible_organization_unit_ids(request.user,tenant,"asset.manage")
        from apps.organizations.models import OrganizationUnit
        units=OrganizationUnit.objects.for_tenant(tenant).filter(id__in=allowed,deleted_at__isnull=True).order_by("code")
        memberships=TenantMembership.objects.filter(tenant=tenant,is_active=True).select_related("user").order_by("user__username")
        return Response({
            "organization_units":[{"id":str(u.id),"code":u.code,"name":u.name} for u in units],
            "users":[{"id":m.user_id,"username":m.user.username,"display":m.user.get_full_name() or m.user.get_username()} for m in memberships],
        })
    def perform_create(self,serializer):
        tenant=self._tenant();unit=serializer.validated_data["organization_unit"];require_tenant_permission(self.request.user,tenant,"asset.manage",unit);obj=serializer.save(tenant=tenant);record_audit_event(self.request.user,tenant,"asset.create","asset",obj.id,new_data={"code":obj.code,"title":obj.title},object_repr=str(obj),request=self.request)
    def perform_update(self,serializer):
        tenant=self._tenant();instance=serializer.instance;require_tenant_permission(self.request.user,tenant,"asset.manage",instance.organization_unit)
        new_unit=serializer.validated_data.get("organization_unit",instance.organization_unit)
        require_tenant_permission(self.request.user,tenant,"asset.manage",new_unit)
        obj=serializer.save();record_audit_event(self.request.user,tenant,"asset.update","asset",obj.id,request=self.request)
    def perform_destroy(self,instance):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"asset.manage",instance.organization_unit);instance.deleted_at=timezone.now();instance.status=Asset.Status.ARCHIVED;instance.save(update_fields=["deleted_at","status","updated_at"])

class AssetDependencyViewSet(TenantMixin,viewsets.ModelViewSet):
    serializer_class=AssetDependencySerializer
    def get_queryset(self):
        tenant=self._tenant();require_tenant_permission(self.request.user,tenant,"asset.view");allowed=accessible_organization_unit_ids(self.request.user,tenant,"asset.view")
        qs=AssetDependency.objects.filter(tenant=tenant,deleted_at__isnull=True,parent_asset__organization_unit_id__in=allowed,child_asset__organization_unit_id__in=allowed).select_related("parent_asset","child_asset")
        asset=self.request.query_params.get("asset")
        if asset: qs=qs.filter(Q(parent_asset_id=asset)|Q(child_asset_id=asset))
        if self.request.query_params.get("parent_asset"): qs=qs.filter(parent_asset_id=self.request.query_params["parent_asset"])
        if self.request.query_params.get("child_asset"): qs=qs.filter(child_asset_id=self.request.query_params["child_asset"])
        return qs
    def perform_create(self,serializer):
        tenant=self._tenant();parent=serializer.validated_data["parent_asset"];require_tenant_permission(self.request.user,tenant,"asset.manage",parent.organization_unit);serializer.save(tenant=tenant)
    def perform_update(self, serializer):
        tenant=self._tenant(); instance=serializer.instance; require_tenant_permission(self.request.user,tenant,"asset.manage",instance.parent_asset.organization_unit); serializer.save()
    def perform_destroy(self, instance):
        tenant=self._tenant(); require_tenant_permission(self.request.user,tenant,"asset.manage",instance.parent_asset.organization_unit); instance.delete()
