from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('evidence','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='evidence',old_name='evidence_scope_class_idx',new_name='evidence_ev_tenant__daa2f5_idx'),
        migrations.RenameIndex(model_name='evidence',old_name='evidence_owner_class_idx',new_name='evidence_ev_tenant__7e3ad0_idx'),
        migrations.RenameIndex(model_name='evidence',old_name='evidence_valid_idx',new_name='evidence_ev_tenant__b62292_idx'),
        migrations.RenameIndex(model_name='evidence',old_name='evidence_hash_idx',new_name='evidence_ev_tenant__ed2fae_idx'),
        migrations.RenameIndex(model_name='evidencelink',old_name='evidence_link_obj_idx',new_name='evidence_ev_tenant__3a2914_idx'),
    ]
