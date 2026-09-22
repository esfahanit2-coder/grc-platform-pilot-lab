from django.conf import settings
from django.db import models
from apps.common.models import UUIDTimeStampedModel
from apps.tenancy.models import Tenant
from apps.organizations.models import OrganizationUnit
class Document(UUIDTimeStampedModel):
    class Type(models.TextChoices):
        POLICY="policy","Policy"; PROCEDURE="procedure","Procedure"; STANDARD="standard","Standard"; GUIDELINE="guideline","Guideline"; PLAN="plan","Plan"; CHARTER="charter","Charter"; FORM="form","Form"; RECORD="record","Record"; REPORT="report","Report"; MINUTES="minutes","Minutes"
    class Status(models.TextChoices):
        DRAFT="draft","Draft"; REVIEW="review","In review"; APPROVED="approved","Approved"; PUBLISHED="published","Published"; DEPRECATED="deprecated","Deprecated"
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name="documents");organization_unit=models.ForeignKey(OrganizationUnit,null=True,blank=True,on_delete=models.PROTECT,related_name="documents")
    document_type=models.CharField(max_length=24,choices=Type.choices);code=models.CharField(max_length=120);title=models.CharField(max_length=255);owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="owned_documents");status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT);review_date=models.DateField(null=True,blank=True);current_version=models.ForeignKey('DocumentVersion',null=True,blank=True,on_delete=models.SET_NULL,related_name='+');metadata=models.JSONField(default=dict,blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['tenant','code'],name='uq_document_tenant_code')];indexes=[models.Index(fields=['tenant','organization_unit','status']),models.Index(fields=['tenant','review_date'])]
class DocumentVersion(UUIDTimeStampedModel):
    class Status(models.TextChoices): DRAFT="draft","Draft"; REVIEW="review","Review"; APPROVED="approved","Approved"; PUBLISHED="published","Published"; SUPERSEDED="superseded","Superseded"
    document=models.ForeignKey(Document,on_delete=models.CASCADE,related_name="versions");version=models.CharField(max_length=40);content=models.TextField(blank=True);storage_key=models.CharField(max_length=512,blank=True);change_summary=models.TextField(blank=True);created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="created_document_versions");status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT)
    class Meta: constraints=[models.UniqueConstraint(fields=['document','version'],name='uq_document_version')];indexes=[models.Index(fields=['document','status'])]
class DocumentApproval(UUIDTimeStampedModel):
    class Decision(models.TextChoices): PENDING="pending","Pending"; APPROVED="approved","Approved"; REJECTED="rejected","Rejected"; CHANGES="changes_requested","Changes requested"
    version=models.ForeignKey(DocumentVersion,on_delete=models.CASCADE,related_name="approvals");approver=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="document_approvals");approval_order=models.PositiveIntegerField(default=1);decision=models.CharField(max_length=24,choices=Decision.choices,default=Decision.PENDING);comment=models.TextField(blank=True);decided_at=models.DateTimeField(null=True,blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['version','approver'],name='uq_document_version_approver')];ordering=['approval_order','created_at']
class DocumentLink(UUIDTimeStampedModel):
    tenant=models.ForeignKey(Tenant,on_delete=models.CASCADE,related_name='document_links');document=models.ForeignKey(Document,on_delete=models.CASCADE,related_name='links');object_type=models.CharField(max_length=60);object_id=models.UUIDField();relation_type=models.CharField(max_length=32,default='supports')
    class Meta: constraints=[models.UniqueConstraint(fields=['tenant','document','object_type','object_id','relation_type'],name='uq_document_object_link')];indexes=[models.Index(fields=['tenant','object_type','object_id'])]
class ReportTemplate(UUIDTimeStampedModel):
    class TemplateType(models.TextChoices): RTP='rtp','RTP'; SOA='soa','SoA'; AUDIT='audit','Audit report'; ASSESSMENT='assessment','Assessment report'; EXECUTIVE='executive','Executive report'; CUSTOM='custom','Custom'
    tenant=models.ForeignKey(Tenant,null=True,blank=True,on_delete=models.CASCADE,related_name='report_templates');template_type=models.CharField(max_length=24,choices=TemplateType.choices);name=models.CharField(max_length=255);language=models.CharField(max_length=12,default='fa');storage_key=models.CharField(max_length=512,blank=True);configuration=models.JSONField(default=dict,blank=True);version=models.CharField(max_length=40,default='1.0');is_active=models.BooleanField(default=True)
