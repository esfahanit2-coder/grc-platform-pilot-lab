from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('organizations','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='organizationunit',old_name='organizatio_tenant__8f0e13_idx',new_name='organizatio_tenant__b740df_idx'),
        migrations.RenameIndex(model_name='organizationunit',old_name='organizatio_tenant__a91a95_idx',new_name='organizatio_tenant__13d7b5_idx'),
    ]
