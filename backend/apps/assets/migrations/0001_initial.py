from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import uuid
class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL),('tenancy','0001_initial'),('organizations','0001_initial')]
    operations=[
        migrations.CreateModel(name='Asset',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),
            ('asset_type',models.CharField(choices=[('information','Information'),('hardware','Hardware'),('software','Software'),('application','Application'),('database','Database'),('cloud_service','Cloud service'),('service','Service'),('process','Process'),('person','Person'),('site','Site'),('other','Other')],max_length=24)),('code',models.CharField(max_length=100)),('title',models.CharField(max_length=255)),('description',models.TextField(blank=True)),('confidentiality',models.PositiveSmallIntegerField(default=3,validators=[django.core.validators.MinValueValidator(1),django.core.validators.MaxValueValidator(5)])),('integrity',models.PositiveSmallIntegerField(default=3,validators=[django.core.validators.MinValueValidator(1),django.core.validators.MaxValueValidator(5)])),('availability',models.PositiveSmallIntegerField(default=3,validators=[django.core.validators.MinValueValidator(1),django.core.validators.MaxValueValidator(5)])),('criticality',models.DecimalField(decimal_places=2,default=3,max_digits=6)),('status',models.CharField(choices=[('active','Active'),('retired','Retired'),('archived','Archived')],default='active',max_length=20)),('metadata',models.JSONField(blank=True,default=dict)),
            ('custodian',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='custodied_assets',to=settings.AUTH_USER_MODEL)),('organization_unit',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='assets',to='organizations.organizationunit')),('owner',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='owned_assets',to=settings.AUTH_USER_MODEL)),('tenant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='assets',to='tenancy.tenant')),
        ]),
        migrations.CreateModel(name='AssetDependency',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),('dependency_type',models.CharField(default='depends_on',max_length=80)),('critical',models.BooleanField(default=False)),('child_asset',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='dependencies_in',to='assets.asset')),('parent_asset',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='dependencies_out',to='assets.asset')),('tenant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='asset_dependencies',to='tenancy.tenant')),
        ]),
        migrations.AddConstraint(model_name='asset',constraint=models.UniqueConstraint(fields=('tenant','code'),name='uq_asset_tenant_code')),
        migrations.AddConstraint(model_name='assetdependency',constraint=models.UniqueConstraint(fields=('tenant','parent_asset','child_asset','dependency_type'),name='uq_asset_dependency')),
        migrations.AddIndex(model_name='asset',index=models.Index(fields=['tenant','organization_unit','status'],name='assets_asse_tenant__82a4b0_idx')),
        migrations.AddIndex(model_name='asset',index=models.Index(fields=['tenant','asset_type'],name='assets_asse_tenant__4be207_idx')),
    ]
