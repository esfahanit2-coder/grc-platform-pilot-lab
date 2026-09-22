from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('actions', '0001_initial')]
    operations = [
        migrations.RenameIndex(model_name='action', old_name='actions_act_tenant__9070e1_idx', new_name='actions_act_tenant__0755a1_idx'),
        migrations.RenameIndex(model_name='action', old_name='actions_act_tenant__8b45ba_idx', new_name='actions_act_tenant__5f747c_idx'),
        migrations.RenameIndex(model_name='action', old_name='actions_act_tenant__aa292d_idx', new_name='actions_act_tenant__4df80e_idx'),
    ]
