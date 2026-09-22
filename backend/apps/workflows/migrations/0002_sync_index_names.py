from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('workflows','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='workflowdefinition',old_name='workflows_w_tenant__20f2a4_idx',new_name='workflows_w_tenant__e1c386_idx'),
        migrations.RenameIndex(model_name='workflowinstance',old_name='workflows_w_tenant__0609a0_idx',new_name='workflows_w_tenant__a3d450_idx'),
        migrations.RenameIndex(model_name='workflowinstance',old_name='workflows_w_tenant__4ae518_idx',new_name='workflows_w_tenant__f531c2_idx'),
    ]
