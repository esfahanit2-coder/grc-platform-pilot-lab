from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    initial=True
    dependencies=[
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenancy','0001_initial'),('organizations','0001_initial'),('frameworks','0001_initial'),
    ]
    operations=[
        migrations.CreateModel(name='ControlCategory',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),
            ('code',models.SlugField(max_length=100)),('name',models.CharField(max_length=200)),('description',models.TextField(blank=True)),
            ('parent',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='children',to='controls.controlcategory')),
            ('tenant',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='control_categories',to='tenancy.tenant')),
        ],options={'ordering':['code']}),
        migrations.CreateModel(name='Control',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),
            ('code',models.SlugField(max_length=120)),('title',models.CharField(max_length=255)),('description',models.TextField(blank=True)),('objective',models.TextField(blank=True)),
            ('control_type',models.CharField(choices=[('administrative','Administrative'),('technical','Technical'),('physical','Physical'),('process','Process')],default='administrative',max_length=24)),
            ('nature',models.CharField(choices=[('preventive','Preventive'),('detective','Detective'),('corrective','Corrective'),('directive','Directive')],default='preventive',max_length=24)),('frequency',models.CharField(blank=True,max_length=80)),
            ('automation_level',models.CharField(choices=[('manual','Manual'),('semi_automated','Semi-automated'),('automated','Automated')],default='manual',max_length=24)),('status',models.CharField(choices=[('draft','Draft'),('active','Active'),('archived','Archived')],default='draft',max_length=20)),('metadata',models.JSONField(blank=True,default=dict)),
            ('category',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='controls',to='controls.controlcategory')),('created_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='created_controls',to=settings.AUTH_USER_MODEL)),('tenant',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='controls',to='tenancy.tenant')),
        ],options={'ordering':['code']}),
        migrations.CreateModel(name='ControlRequirement',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),
            ('coverage',models.DecimalField(decimal_places=2,default=100,max_digits=5,validators=[django.core.validators.MinValueValidator(0),django.core.validators.MaxValueValidator(100)])),('mapping_type',models.CharField(choices=[('exact','Exact'),('strong','Strong'),('partial','Partial'),('related','Related')],default='related',max_length=16)),('rationale',models.TextField(blank=True)),('source',models.CharField(default='manual',max_length=24)),('approved',models.BooleanField(default=False)),
            ('control',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='requirement_mappings',to='controls.control')),('requirement',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='control_mappings',to='frameworks.requirement')),('tenant',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='control_requirement_mappings',to='tenancy.tenant')),
        ]),
        migrations.CreateModel(name='ControlImplementation',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),
            ('implementation_description',models.TextField(blank=True)),('implementation_status',models.CharField(choices=[('not_implemented','Not implemented'),('planned','Planned'),('in_progress','In progress'),('implemented','Implemented'),('suspended','Suspended')],default='not_implemented',max_length=24)),('effectiveness',models.CharField(choices=[('not_assessed','Not assessed'),('ineffective','Ineffective'),('partial','Partially effective'),('effective','Effective')],default='not_assessed',max_length=24)),('implementation_date',models.DateField(blank=True,null=True)),('review_date',models.DateField(blank=True,null=True)),('metadata',models.JSONField(blank=True,default=dict)),
            ('control',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='implementations',to='controls.control')),('operator',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='operated_control_implementations',to=settings.AUTH_USER_MODEL)),('organization_unit',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='control_implementations',to='organizations.organizationunit')),('owner',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='owned_control_implementations',to=settings.AUTH_USER_MODEL)),('tenant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='control_implementations',to='tenancy.tenant')),
        ]),
        migrations.AddConstraint(model_name='controlcategory',constraint=models.UniqueConstraint(fields=('tenant','code'),name='uq_control_category_tenant_code')),
        migrations.AddConstraint(model_name='controlcategory',constraint=models.UniqueConstraint(condition=models.Q(('tenant__isnull',True)),fields=('code',),name='uq_control_category_global_code')),
        migrations.AddConstraint(model_name='control',constraint=models.UniqueConstraint(fields=('tenant','code'),name='uq_control_tenant_code')),
        migrations.AddConstraint(model_name='control',constraint=models.UniqueConstraint(condition=models.Q(('tenant__isnull',True)),fields=('code',),name='uq_control_global_code')),
        migrations.AddConstraint(model_name='controlrequirement',constraint=models.UniqueConstraint(fields=('tenant','control','requirement'),name='uq_control_requirement_tenant')),
        migrations.AddConstraint(model_name='controlrequirement',constraint=models.UniqueConstraint(condition=models.Q(('tenant__isnull',True)),fields=('control','requirement'),name='uq_control_requirement_global')),
        migrations.AddConstraint(model_name='controlimplementation',constraint=models.UniqueConstraint(fields=('tenant','control','organization_unit'),name='uq_control_implementation_scope')),
        migrations.AddIndex(model_name='control',index=models.Index(fields=['tenant','status'],name='controls_co_tenant__11e1d6_idx')),
        migrations.AddIndex(model_name='control',index=models.Index(fields=['tenant','control_type'],name='controls_co_tenant__b6e45d_idx')),
        migrations.AddIndex(model_name='controlrequirement',index=models.Index(fields=['tenant','control'],name='controls_cr_tenant__69568c_idx')),
        migrations.AddIndex(model_name='controlrequirement',index=models.Index(fields=['tenant','requirement'],name='controls_cr_tenant__ee9cd2_idx')),
        migrations.AddIndex(model_name='controlimplementation',index=models.Index(fields=['tenant','organization_unit','implementation_status'],name='controls_ci_tenant__b0df60_idx')),
        migrations.AddIndex(model_name='controlimplementation',index=models.Index(fields=['tenant','owner'],name='controls_ci_tenant__2c220c_idx')),
    ]
