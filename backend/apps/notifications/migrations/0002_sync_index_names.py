from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('notifications','0001_initial')]
    operations=[migrations.RenameIndex(model_name='notification',old_name='notificatio_tenant__fe3341_idx',new_name='notificatio_tenant__7fa79e_idx')]
