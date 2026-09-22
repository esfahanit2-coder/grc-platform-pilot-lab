from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant

class Action(UUIDTimeStampedModel):
    class Priority(models.TextChoices):
        LOW="low","Low";MEDIUM="medium","Medium";HIGH="high","High";CRITICAL="critical","Critical"
    class Status(models.TextChoices):
        TODO="todo","To do";IN_PROGRESS="in_progress","In progress";REVIEW="review","Review";DONE="done","Done";CANCELLED="cancelled","Cancelled"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="actions")
    organization_unit=models.ForeignKey(OrganizationUnit,null=True,blank=True,on_delete=models.PROTECT,related_name="actions")
    title=models.CharField(max_length=255)
    description=models.TextField(blank=True)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_grc_actions")
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reviewed_grc_actions")
    priority=models.CharField(max_length=16,choices=Priority.choices,default=Priority.MEDIUM)
    start_date=models.DateField(null=True,blank=True)
    due_date=models.DateField(null=True,blank=True)
    progress=models.PositiveSmallIntegerField(default=0)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.TODO)
    completed_at=models.DateTimeField(null=True,blank=True)
    source_type=models.CharField(max_length=60,blank=True)
    source_id=models.UUIDField(null=True,blank=True)
    metadata=models.JSONField(default=dict,blank=True)
    class Meta:
        indexes=[models.Index(fields=["tenant","organization_unit","status"]),models.Index(fields=["tenant","owner","due_date"]),models.Index(fields=["tenant","source_type","source_id"])]
