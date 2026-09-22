from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('assessments','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='assessment',old_name='assess_tenant_scope_idx',new_name='assessments_tenant__d8128e_idx'),
        migrations.RenameIndex(model_name='assessment',old_name='assess_owner_due_idx',new_name='assessments_tenant__bab8ad_idx'),
        migrations.RenameIndex(model_name='assessment',old_name='assess_framework_idx',new_name='assessments_tenant__f7b6fc_idx'),
        migrations.RenameIndex(model_name='assessmentitem',old_name='assess_item_status_idx',new_name='assessments_assessm_066d8f_idx'),
        migrations.RenameIndex(model_name='assessmentitem',old_name='assess_item_user_idx',new_name='assessments_assessm_355d64_idx'),
    ]
