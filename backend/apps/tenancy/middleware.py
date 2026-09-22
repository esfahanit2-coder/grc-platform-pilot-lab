import uuid
from django.http import JsonResponse

class TenantHeaderMiddleware:
    header_name = "HTTP_X_TENANT_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.META.get(self.header_name)
        request.tenant_id = None
        if raw:
            try:
                request.tenant_id = uuid.UUID(raw)
            except (TypeError, ValueError, AttributeError):
                return JsonResponse({
                    "code": "INVALID_TENANT_ID",
                    "message": "X-Tenant-ID must be a valid UUID.",
                    "field": "X-Tenant-ID",
                    "details": {},
                }, status=400)
        return self.get_response(request)
