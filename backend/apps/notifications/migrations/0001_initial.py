from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion,uuid
class Migration(migrations.Migration):
 initial=True
 dependencies=[('tenancy','0001_initial'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
 operations=[migrations.CreateModel(name='Notification',fields=[('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('deleted_at',models.DateTimeField(blank=True,null=True)),('category',models.CharField(default='general',max_length=60)),('title',models.CharField(max_length=255)),('body',models.TextField(blank=True)),('object_type',models.CharField(blank=True,max_length=80)),('object_id',models.UUIDField(blank=True,null=True)),('severity',models.CharField(default='info',max_length=20)),('read_at',models.DateTimeField(blank=True,null=True)),('metadata',models.JSONField(blank=True,default=dict)),('tenant',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='notifications',to='tenancy.tenant')),('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='grc_notifications',to=settings.AUTH_USER_MODEL))],options={'indexes':[models.Index(fields=['tenant','user','read_at','created_at'],name='notificatio_tenant__fe3341_idx')]})]
