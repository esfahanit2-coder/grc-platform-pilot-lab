from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant

class ConnectorConfig(UUIDTimeStampedModel):
    class ConnectorType(models.TextChoices):
        ACTIVE_DIRECTORY="active_directory","Active Directory / LDAP"
        TENABLE="tenable","Tenable / Nessus API"
        VEEAM="veeam","Veeam Enterprise Manager"
        FORTIGATE="fortigate","FortiGate REST API"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="connector_configs")
    organization_unit=models.ForeignKey(OrganizationUnit,null=True,blank=True,on_delete=models.PROTECT,related_name="connector_configs")
    name=models.CharField(max_length=160)
    connector_type=models.CharField(max_length=32,choices=ConnectorType.choices)
    base_url=models.CharField(max_length=500,blank=True)
    username_env_var=models.CharField(max_length=120,blank=True)
    secret_env_var=models.CharField(max_length=120,blank=True)
    secondary_secret_env_var=models.CharField(max_length=120,blank=True)
    verify_tls=models.BooleanField(default=True)
    is_active=models.BooleanField(default=True)
    configuration=models.JSONField(default=dict,blank=True)
    last_sync_at=models.DateTimeField(null=True,blank=True)
    last_status=models.CharField(max_length=24,blank=True)
    last_error=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tenant","name"],name="uq_connector_tenant_name")]
        indexes=[models.Index(fields=["tenant","connector_type","is_active"])]

class ConnectorRun(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        RUNNING="running","Running"; SUCCEEDED="succeeded","Succeeded"; FAILED="failed","Failed"
    connector=models.ForeignKey(ConnectorConfig,on_delete=models.CASCADE,related_name="runs")
    triggered_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="connector_runs")
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.RUNNING)
    started_at=models.DateTimeField(auto_now_add=True)
    finished_at=models.DateTimeField(null=True,blank=True)
    summary=models.JSONField(default=dict,blank=True)
    error=models.TextField(blank=True)
    class Meta:
        indexes=[models.Index(fields=["connector","status","started_at"])]
