from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('assets','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='asset',old_name='assets_asse_tenant__82a4b0_idx',new_name='assets_asse_tenant__84026f_idx'),
        migrations.RenameIndex(model_name='asset',old_name='assets_asse_tenant__4be207_idx',new_name='assets_asse_tenant__0cec78_idx'),
    ]
