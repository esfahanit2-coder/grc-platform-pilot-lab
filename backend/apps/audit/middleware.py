import logging
import time
import uuid


request_logger = logging.getLogger("grc.request")


class CorrelationIdMiddleware:
    header_name = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        raw = request.META.get(self.header_name)
        try:
            request.correlation_id = uuid.UUID(raw) if raw else uuid.uuid4()
        except (TypeError, ValueError, AttributeError):
            request.correlation_id = uuid.uuid4()

        try:
            response = self.get_response(request)
        except Exception as exc:
            request_logger.exception(
                "request_failed",
                extra={
                    "request_id": str(request.correlation_id),
                    "method": request.method,
                    "path": request.path,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise

        response["X-Request-ID"] = str(request.correlation_id)
        request_logger.info(
            "request_completed",
            extra={
                "request_id": str(request.correlation_id),
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            },
        )
        return response
