from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('risks','0001_initial')]
    operations=[
        migrations.RenameIndex(model_name='risk',old_name='risks_risk_tenant__6aeabb_idx',new_name='risks_risk_tenant__c54c97_idx'),
        migrations.RenameIndex(model_name='risk',old_name='risks_risk_tenant__072c8b_idx',new_name='risks_risk_tenant__e92d21_idx'),
        migrations.RenameIndex(model_name='riskevaluation',old_name='risks_riske_risk_id_50c9fc_idx',new_name='risks_riske_risk_id_e6e45d_idx'),
        migrations.RenameIndex(model_name='riskmethodology',old_name='risks_risk_tenant__076c98_idx',new_name='risks_riskm_tenant__09000d_idx'),
    ]
