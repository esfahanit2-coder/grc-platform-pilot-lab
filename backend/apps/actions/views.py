from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.audit.services import record_audit_event
from apps.identity.services import accessible_organization_unit_ids,has_whole_tenant_permission,require_tenant_permission,require_whole_tenant_permission
from apps.tenancy.models import TenantMembership
from apps.tenancy.services import resolve_tenant_for_request
from apps.notifications.services import notify_user
from .models import Action
from .serializers import ActionSerializer
class ActionViewSet(viewsets.ModelViewSet):
    serializer_class=ActionSerializer
    def _tenant(self):
        if not hasattr(self,"_resolved_tenant"): self._resolved_tenant=resolve_tenant_for_request(self.request)
        return self._resolved_tenant
    def get_serializer_context(self): ctx=super().get_serializer_context();ctx["tenant"]=self._tenant();return ctx
    def _perm(self): return "action.view" if self.action in {"list","retrieve"} else "action.manage"
    def get_queryset(self):
        tenant=self._tenant();code=self._perm();require_tenant_permission(self.request.user,tenant,code);allowed=accessible_organization_unit_ids(self.request.user,tenant,code);whole=has_whole_tenant_permission(self.request.user,tenant,code)
        qs=Action.objects.filter(tenant=tenant,deleted_at__isnull=True)
        if not whole: qs=qs.filter(organization_unit_id__in=allowed)
        search=self.request.query_params.get("search")
        if search: qs=qs.filter(Q(title__icontains=search)|Q(description__icontains=search))
        if self.request.query_params.get("status"): qs=qs.filter(status=self.request.query_params["status"])
        if self.request.query_params.get("priority"): qs=qs.filter(priority=self.request.query_params["priority"])
        if self.request.query_params.get("owner"): qs=qs.filter(owner_id=self.request.query_params["owner"])
        if self.request.query_params.get("organization_unit"): qs=qs.filter(organization_unit_id=self.request.query_params["organization_unit"])
        due=self.request.query_params.get("due")
        today=timezone.localdate()
        if due=="overdue": qs=qs.exclude(status__in=[Action.Status.DONE,Action.Status.CANCELLED]).filter(due_date__lt=today)
        elif due=="due_soon": qs=qs.exclude(status__in=[Action.Status.DONE,Action.Status.CANCELLED]).filter(due_date__gte=today,due_date__lte=today+timedelta(days=7))
        elif due=="undated": qs=qs.filter(due_date__isnull=True)
        return qs.select_related("organization_unit","owner","reviewer").order_by("due_date","created_at")
    @action(detail=False,methods=["get"],url_path="selector-options")
    def selector_options(self,request):
        tenant=self._tenant()
        require_tenant_permission(request.user,tenant,"action.manage")
        allowed=accessible_organization_unit_ids(request.user,tenant,"action.manage")
        from apps.organizations.models import OrganizationUnit
        units=OrganizationUnit.objects.for_tenant(tenant).filter(id__in=allowed,deleted_at__isnull=True).order_by("code")
        memberships=TenantMembership.objects.filter(tenant=tenant,is_active=True).select_related("user").order_by("user__username")
        return Response({
            "organization_units":[{"id":str(u.id),"code":u.code,"name":u.name} for u in units],
            "users":[{"id":m.user_id,"username":m.user.username,"display":m.user.get_full_name() or m.user.get_username()} for m in memberships],
        })
    def perform_create(self,serializer):
        tenant=self._tenant();unit=serializer.validated_data.get("organization_unit");require_tenant_permission(self.request.user,tenant,"action.manage",unit) if unit else require_whole_tenant_permission(self.request.user,tenant,"action.manage");obj=serializer.save(tenant=tenant);record_audit_event(self.request.user,tenant,"action.create","action",obj.id,request=self.request)
        notify_user(
            tenant=tenant,
            user=obj.owner,
            category="action_assigned",
            title=f"اقدام جدید به شما تخصیص داده شد: {obj.title}",
            body=f"اولویت: {obj.priority}" + (f" — سررسید: {obj.due_date}" if obj.due_date else ""),
            object_type="action",
            object_id=obj.id,
            severity="warning" if obj.priority in {Action.Priority.HIGH, Action.Priority.CRITICAL} else "info",
        )
    def perform_update(self, serializer):
        tenant = self._tenant()
        instance = serializer.instance
        previous_owner_id = instance.owner_id
        if instance.organization_unit:
            require_tenant_permission(self.request.user, tenant, "action.manage", instance.organization_unit)
        else:
            require_whole_tenant_permission(self.request.user, tenant, "action.manage")
        new_unit = serializer.validated_data.get("organization_unit", instance.organization_unit)
        if new_unit:
            require_tenant_permission(self.request.user, tenant, "action.manage", new_unit)
        elif instance.organization_unit_id:
            require_whole_tenant_permission(self.request.user, tenant, "action.manage")
        obj = serializer.save()
        if obj.status == Action.Status.DONE and obj.completed_at is None:
            obj.completed_at = timezone.now()
            obj.progress = 100
            obj.save(update_fields=["completed_at", "progress", "updated_at"])
        record_audit_event(self.request.user, tenant, "action.update", "action", obj.id, request=self.request)
        if obj.owner_id != previous_owner_id:
            notify_user(
                tenant=tenant,
                user=obj.owner,
                category="action_assigned",
                title=f"اقدام به شما واگذار شد: {obj.title}",
                body=f"اولویت: {obj.priority}" + (f" — سررسید: {obj.due_date}" if obj.due_date else ""),
                object_type="action",
                object_id=obj.id,
                severity="warning" if obj.priority in {Action.Priority.HIGH, Action.Priority.CRITICAL} else "info",
            )

    def perform_destroy(self, instance):
        tenant=self._tenant()
        if instance.organization_unit:
            require_tenant_permission(self.request.user,tenant,"action.manage",instance.organization_unit)
        else:
            require_whole_tenant_permission(self.request.user,tenant,"action.manage")
        instance.deleted_at=timezone.now(); instance.status=Action.Status.CANCELLED; instance.save(update_fields=["deleted_at","status","updated_at"])
