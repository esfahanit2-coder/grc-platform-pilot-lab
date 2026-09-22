from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.tenancy.models import Tenant
from apps.organizations.models import OrganizationUnit
from apps.frameworks.models import FrameworkVersion, Requirement
from apps.controls.models import ControlImplementation

class AuditPlan(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT="draft","Draft"; APPROVED="approved","Approved"; ACTIVE="active","Active"; CLOSED="closed","Closed"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="audit_plans")
    organization_unit=models.ForeignKey(OrganizationUnit,null=True,blank=True,on_delete=models.PROTECT,related_name="audit_plans")
    title=models.CharField(max_length=255)
    period_start=models.DateField(); period_end=models.DateField()
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_audit_plans")
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="approved_audit_plans")
    approved_at=models.DateTimeField(null=True,blank=True)
    metadata=models.JSONField(default=dict,blank=True)
    class Meta:
        indexes=[models.Index(fields=["tenant","organization_unit","status"]),models.Index(fields=["tenant","period_start","period_end"])]
    def __str__(self): return self.title

class AuditEngagement(UUIDTimeStampedModel):
    class AuditType(models.TextChoices):
        INTERNAL="internal","Internal"; FRAMEWORK="framework","Framework"; CONTROL="control","Control"; PROCESS="process","Process"; FOLLOW_UP="follow_up","Follow-up"
    class Status(models.TextChoices):
        DRAFT="draft","Draft"; PLANNED="planned","Planned"; IN_PROGRESS="in_progress","In progress"; REVIEW="review","Review"; COMPLETED="completed","Completed"; CANCELLED="cancelled","Cancelled"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="audit_engagements")
    plan=models.ForeignKey(AuditPlan,null=True,blank=True,on_delete=models.SET_NULL,related_name="engagements")
    organization_unit=models.ForeignKey(OrganizationUnit,null=True,blank=True,on_delete=models.PROTECT,related_name="audit_engagements")
    framework_version=models.ForeignKey(FrameworkVersion,null=True,blank=True,on_delete=models.PROTECT,related_name="audit_engagements")
    title=models.CharField(max_length=255)
    audit_type=models.CharField(max_length=20,choices=AuditType.choices,default=AuditType.INTERNAL)
    objective=models.TextField(blank=True); scope=models.TextField(blank=True)
    lead_auditor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="led_audits")
    start_date=models.DateField(null=True,blank=True); end_date=models.DateField(null=True,blank=True)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    conclusion=models.TextField(blank=True); metadata=models.JSONField(default=dict,blank=True)
    requirements=models.ManyToManyField(Requirement,blank=True,related_name="audit_engagements")
    controls=models.ManyToManyField(ControlImplementation,blank=True,related_name="audit_engagements")
    class Meta:
        indexes=[models.Index(fields=["tenant","organization_unit","status"]),models.Index(fields=["tenant","lead_auditor","start_date"])]
    def __str__(self): return self.title

class AuditTeamMember(UUIDTimeStampedModel):
    engagement=models.ForeignKey(AuditEngagement,on_delete=models.CASCADE,related_name="team_members")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="audit_team_memberships")
    role=models.CharField(max_length=80,default="auditor")
    class Meta:
        constraints=[models.UniqueConstraint(fields=["engagement","user"],name="uq_audit_team_member")]

class Workpaper(UUIDTimeStampedModel):
    class Result(models.TextChoices):
        NOT_TESTED="not_tested","Not tested"; PASS="pass","Pass"; FAIL="fail","Fail"; PARTIAL="partial","Partial"; NA="not_applicable","Not applicable"
    class Status(models.TextChoices):
        DRAFT="draft","Draft"; READY="ready","Ready for review"; REVIEWED="reviewed","Reviewed"
    engagement=models.ForeignKey(AuditEngagement,on_delete=models.CASCADE,related_name="workpapers")
    requirement=models.ForeignKey(Requirement,null=True,blank=True,on_delete=models.PROTECT,related_name="audit_workpapers")
    control_implementation=models.ForeignKey(ControlImplementation,null=True,blank=True,on_delete=models.PROTECT,related_name="audit_workpapers")
    title=models.CharField(max_length=255); objective=models.TextField(blank=True); procedure=models.TextField(blank=True); sample=models.TextField(blank=True)
    tester=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="tested_workpapers")
    result=models.CharField(max_length=20,choices=Result.choices,default=Result.NOT_TESTED)
    conclusion=models.TextField(blank=True); status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reviewed_workpapers")
    reviewed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        indexes=[models.Index(fields=["engagement","status"]),models.Index(fields=["engagement","result"])]
    def __str__(self): return self.title
