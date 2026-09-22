from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.assets.models import Asset
from apps.common.models import UUIDTimeStampedModel
from apps.controls.models import ControlImplementation
from apps.organizations.models import OrganizationUnit
from apps.tenancy.models import Tenant

class RiskCategory(UUIDTimeStampedModel):
    tenant=models.ForeignKey(Tenant,null=True,blank=True,on_delete=models.CASCADE,related_name="risk_categories")
    parent=models.ForeignKey("self",null=True,blank=True,on_delete=models.PROTECT,related_name="children")
    code=models.SlugField(max_length=100)
    name=models.CharField(max_length=200)
    description=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tenant","code"],name="uq_risk_category_tenant_code"),models.UniqueConstraint(fields=["code"],condition=Q(tenant__isnull=True),name="uq_risk_category_global_code")]
    def clean(self):
        if self.parent_id and self.parent_id==self.id: raise ValidationError({"parent":"A category cannot be its own parent."})
        if self.parent_id and self.parent.tenant_id!=self.tenant_id: raise ValidationError({"parent":"Parent category must have same ownership scope."})
        node=self.parent;visited=set()
        while node is not None and node.id not in visited:
            if self.id and node.id==self.id: raise ValidationError({"parent":"Risk category hierarchy cannot contain cycles."})
            visited.add(node.id);node=node.parent
    def save(self,*args,**kwargs): self.full_clean();return super().save(*args,**kwargs)

class RiskMethodology(UUIDTimeStampedModel):
    class MethodologyType(models.TextChoices):
        QUALITATIVE="qualitative","Qualitative"
        SEMI_QUANTITATIVE="semi_quantitative","Semi-quantitative"
        QUANTITATIVE="quantitative","Quantitative"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="risk_methodologies")
    name=models.CharField(max_length=200)
    methodology_type=models.CharField(max_length=24,choices=MethodologyType.choices,default=MethodologyType.SEMI_QUANTITATIVE)
    likelihood_scale=models.JSONField(default=list)
    impact_scale=models.JSONField(default=list)
    matrix=models.JSONField(default=dict,blank=True)
    thresholds=models.JSONField(default=list)
    formula=models.CharField(max_length=80,default="product")
    is_default=models.BooleanField(default=False)
    status=models.CharField(max_length=20,default="active")
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tenant","name"],name="uq_risk_methodology_tenant_name")]
        indexes=[models.Index(fields=["tenant","is_default","status"])]

class Risk(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT="draft","Draft";OPEN="open","Open";TREATMENT="treatment","Treatment";ACCEPTED="accepted","Accepted";CLOSED="closed","Closed";ARCHIVED="archived","Archived"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="risks")
    organization_unit=models.ForeignKey(OrganizationUnit,null=True,blank=True,on_delete=models.PROTECT,related_name="risks")
    asset=models.ForeignKey(Asset,null=True,blank=True,on_delete=models.PROTECT,related_name="risks")
    category=models.ForeignKey(RiskCategory,null=True,blank=True,on_delete=models.PROTECT,related_name="risks")
    code=models.CharField(max_length=100)
    title=models.CharField(max_length=255)
    scenario=models.TextField(blank=True)
    cause=models.TextField(blank=True)
    consequence=models.TextField(blank=True)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_risks")
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    review_date=models.DateField(null=True,blank=True)
    metadata=models.JSONField(default=dict,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["tenant","code"],name="uq_risk_tenant_code")]
        indexes=[models.Index(fields=["tenant","organization_unit","status"]),models.Index(fields=["tenant","owner","review_date"])]
    def __str__(self): return f"{self.code} — {self.title}"

class RiskEvaluation(UUIDTimeStampedModel):
    class EvaluationType(models.TextChoices):
        INHERENT="inherent","Inherent";CURRENT="current","Current";RESIDUAL="residual","Residual";TARGET="target","Target"
    risk=models.ForeignKey(Risk,on_delete=models.CASCADE,related_name="evaluations")
    methodology=models.ForeignKey(RiskMethodology,on_delete=models.PROTECT,related_name="evaluations")
    evaluation_type=models.CharField(max_length=16,choices=EvaluationType.choices)
    likelihood=models.DecimalField(max_digits=10,decimal_places=2)
    impact=models.DecimalField(max_digits=10,decimal_places=2)
    score=models.DecimalField(max_digits=14,decimal_places=4)
    level=models.CharField(max_length=40)
    evaluated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="risk_evaluations")
    evaluated_at=models.DateTimeField(default=timezone.now)
    rationale=models.TextField(blank=True)
    class Meta:
        ordering=["-evaluated_at","-created_at"]
        indexes=[models.Index(fields=["risk","evaluation_type","evaluated_at"])]

class RiskControl(UUIDTimeStampedModel):
    class RelationshipType(models.TextChoices):
        EXISTING="existing","Existing control";TREATMENT="treatment","Treatment control";COMPENSATING="compensating","Compensating control"
    risk=models.ForeignKey(Risk,on_delete=models.CASCADE,related_name="control_links")
    control_implementation=models.ForeignKey(ControlImplementation,on_delete=models.PROTECT,related_name="risk_links")
    relationship_type=models.CharField(max_length=20,choices=RelationshipType.choices,default=RelationshipType.EXISTING)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["risk","control_implementation"],name="uq_risk_control_implementation")]

class RiskTreatment(UUIDTimeStampedModel):
    class Strategy(models.TextChoices):
        AVOID="avoid","Avoid";REDUCE="reduce","Reduce";TRANSFER="transfer","Transfer";ACCEPT="accept","Accept"
    class Status(models.TextChoices):
        DRAFT="draft","Draft";PLANNED="planned","Planned";IN_PROGRESS="in_progress","In progress";COMPLETED="completed","Completed";CANCELLED="cancelled","Cancelled"
    class ApprovalStatus(models.TextChoices):
        NOT_SUBMITTED="not_submitted","Not submitted";PENDING="pending","Pending";APPROVED="approved","Approved";REJECTED="rejected","Rejected"
    risk=models.ForeignKey(Risk,on_delete=models.CASCADE,related_name="treatments")
    strategy=models.CharField(max_length=16,choices=Strategy.choices)
    description=models.TextField(blank=True)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_risk_treatments")
    target_date=models.DateField(null=True,blank=True)
    target_score=models.DecimalField(max_digits=14,decimal_places=4,null=True,blank=True)
    approval_status=models.CharField(max_length=20,choices=ApprovalStatus.choices,default=ApprovalStatus.NOT_SUBMITTED)
    status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    accepted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="accepted_risk_treatments")
    accepted_at=models.DateTimeField(null=True,blank=True)
