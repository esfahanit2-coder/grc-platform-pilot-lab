from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
 dependencies=[('findings','0001_initial'),('internal_audits','0001_initial')]
 operations=[migrations.AddField(model_name='finding',name='audit_workpaper',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='findings',to='internal_audits.workpaper'))]
