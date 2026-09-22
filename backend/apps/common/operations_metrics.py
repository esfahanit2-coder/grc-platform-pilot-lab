import math


STATUS_VALUE = {
    "ok": 1,
    "healthy": 1,
    "warning": 0.5,
    "unknown": 0,
    "degraded": 0.5,
    "critical": 0,
}


def _escape_label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _metric_line(name, value, labels=None):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        value = 0
    suffix = ""
    if labels:
        rendered = ",".join(
            f'{key}="{_escape_label(labels[key])}"' for key in sorted(labels)
        )
        suffix = "{" + rendered + "}"
    return f"{name}{suffix} {value}"


def render_prometheus_metrics(status):
    """Render a bounded, customer-data-free Prometheus 0.0.4 exposition."""
    lines = [
        "# HELP grc_operational_health Deployment operational health (1 healthy, 0.5 degraded, 0 critical).",
        "# TYPE grc_operational_health gauge",
        _metric_line(
            "grc_operational_health",
            STATUS_VALUE.get(status.get("overall_status"), 0),
        ),
        "# HELP grc_component_health Component health (1 ok, 0.5 warning, 0 unknown/critical).",
        "# TYPE grc_component_health gauge",
    ]

    components = status.get("components") or {}
    for name in sorted(components):
        component = components[name] or {}
        lines.append(
            _metric_line(
                "grc_component_health",
                STATUS_VALUE.get(component.get("status"), 0),
                {"component": name},
            )
        )

    queue = components.get("queue") or {}
    queue_details = queue.get("details") or {}
    if isinstance(queue_details.get("depth"), int):
        lines.extend(
            [
                "# HELP grc_celery_queue_depth Current Celery queue depth.",
                "# TYPE grc_celery_queue_depth gauge",
                _metric_line("grc_celery_queue_depth", queue_details["depth"]),
            ]
        )

    age_rows = []
    for name in ("async_pipeline", "backup"):
        age = (components.get(name) or {}).get("age_seconds")
        if isinstance(age, int):
            age_rows.append((name, age))
    if age_rows:
        lines.extend(
            [
                "# HELP grc_operational_signal_age_seconds Age of bounded operational signals.",
                "# TYPE grc_operational_signal_age_seconds gauge",
            ]
        )
        for name, age in age_rows:
            lines.append(
                _metric_line(
                    "grc_operational_signal_age_seconds",
                    age,
                    {"signal": name},
                )
            )

    lines.extend(
        [
            "# HELP grc_build_info Static deployment metadata without tenant/customer labels.",
            "# TYPE grc_build_info gauge",
            _metric_line(
                "grc_build_info",
                1,
                {"environment": status.get("environment") or "unknown"},
            ),
        ]
    )
    return "\n".join(lines) + "\n"
