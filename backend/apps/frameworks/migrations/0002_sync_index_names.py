from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('frameworks','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='framework',old_name='fw_tenant_status_idx',new_name='frameworks__tenant__49294b_idx'),
        migrations.RenameIndex(model_name='framework',old_name='fw_code_status_idx',new_name='frameworks__code_ef723a_idx'),
        migrations.RenameIndex(model_name='frameworkversion',old_name='fwver_status_lock_idx',new_name='frameworks__framewo_bd8251_idx'),
        migrations.RenameIndex(model_name='requirement',old_name='req_ver_parent_sort_idx',new_name='frameworks__framewo_120b25_idx'),
        migrations.RenameIndex(model_name='requirement',old_name='req_ver_assess_idx',new_name='frameworks__framewo_1083db_idx'),
        migrations.RenameIndex(model_name='requirementmapping',old_name='map_tenant_type_idx',new_name='frameworks__tenant__92107c_idx'),
        migrations.RenameIndex(model_name='requirementmapping',old_name='map_tenant_source_idx',new_name='frameworks__tenant__37749e_idx'),
    ]
