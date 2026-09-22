from rest_framework import serializers
from apps.tenancy.models import TenantMembership
from .models import OrganizationUnit


class OrganizationUnitSerializer(serializers.ModelSerializer):
    manager_display = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUnit
        fields = [
            "id", "parent", "unit_type", "code", "name", "name_en", "manager", "manager_display",
            "status", "metadata", "children_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "manager_display", "children_count"]

    def get_manager_display(self, unit):
        if not unit.manager_id:
            return None
        return unit.manager.get_full_name() or unit.manager.get_username()

    def get_children_count(self, unit):
        return unit.children.filter(deleted_at__isnull=True).count()

    def validate_parent(self, parent):
        tenant = self.context.get("tenant")
        if parent and tenant and parent.tenant_id != tenant.id:
            raise serializers.ValidationError("Parent unit must belong to the selected tenant.")
        if self.instance and parent and parent.id == self.instance.id:
            raise serializers.ValidationError("An organization unit cannot be its own parent.")
        if self.instance and parent:
            node = parent
            visited = set()
            while node is not None and node.id not in visited:
                if node.id == self.instance.id:
                    raise serializers.ValidationError("Moving this unit would create a hierarchy cycle.")
                visited.add(node.id)
                node = node.parent
        return parent

    def validate_manager(self, manager):
        tenant = self.context.get("tenant")
        if manager and tenant and not TenantMembership.objects.filter(tenant=tenant, user=manager, is_active=True).exists():
            raise serializers.ValidationError("Manager must be an active member of the selected tenant.")
        return manager


class OrganizationTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUnit
        fields = ["id", "code", "name", "name_en", "unit_type", "status", "manager", "children"]

    def get_children(self, unit):
        allowed_ids = self.context.get("allowed_ids", set())
        children = unit.children.filter(deleted_at__isnull=True).order_by("code")
        if allowed_ids:
            children = children.filter(id__in=allowed_ids)
        return OrganizationTreeSerializer(children, many=True, context=self.context).data
