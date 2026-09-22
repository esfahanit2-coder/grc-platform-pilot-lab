from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('connectors','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='connectorconfig',old_name='connectors_t_tenant__pilot_idx',new_name='connectors__tenant__8d5ba3_idx'),
        migrations.RenameIndex(model_name='connectorrun',old_name='connectors_c_connect_pilot_idx',new_name='connectors__connect_6543de_idx'),
    ]
