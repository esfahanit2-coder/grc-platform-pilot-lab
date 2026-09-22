from django.urls import path
from .views import live, ready
from .operations_views import OperationsMetricsView, OperationsStatusView
from .data_exchange_views import (
    DataExchangeCatalogView,
    DataExchangeCommitView,
    DataExchangeExportView,
    DataExchangeTemplateView,
    DataExchangeValidateView,
)

urlpatterns = [
    path("health/live", live, name="health-live"),
    path("health/ready", ready, name="health-ready"),
    path("operations/status/", OperationsStatusView.as_view(), name="operations-status"),
    path("operations/metrics/", OperationsMetricsView.as_view(), name="operations-metrics"),
    path("data-exchange/catalog/", DataExchangeCatalogView.as_view(), name="data-exchange-catalog"),
    path("data-exchange/template/", DataExchangeTemplateView.as_view(), name="data-exchange-template"),
    path("data-exchange/export/", DataExchangeExportView.as_view(), name="data-exchange-export"),
    path("data-exchange/validate/", DataExchangeValidateView.as_view(), name="data-exchange-validate"),
    path("data-exchange/commit/", DataExchangeCommitView.as_view(), name="data-exchange-commit"),
]
