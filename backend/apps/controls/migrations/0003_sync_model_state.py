from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('controls','0002_control_tests')]
    operations=[
        migrations.RenameIndex(model_name='control',old_name='controls_co_tenant__11e1d6_idx',new_name='controls_co_tenant__737f91_idx'),
        migrations.RenameIndex(model_name='control',old_name='controls_co_tenant__b6e45d_idx',new_name='controls_co_tenant__603246_idx'),
        migrations.RenameIndex(model_name='controlimplementation',old_name='controls_ci_tenant__b0df60_idx',new_name='controls_co_tenant__3aec57_idx'),
        migrations.RenameIndex(model_name='controlimplementation',old_name='controls_ci_tenant__2c220c_idx',new_name='controls_co_tenant__56c053_idx'),
        migrations.RenameIndex(model_name='controlrequirement',old_name='controls_cr_tenant__69568c_idx',new_name='controls_co_tenant__a8ef9d_idx'),
        migrations.RenameIndex(model_name='controlrequirement',old_name='controls_cr_tenant__ee9cd2_idx',new_name='controls_co_tenant__44152d_idx'),
        migrations.AlterField(model_name='controltest',name='automation_type',field=models.CharField(choices=[('manual','Manual'),('semi_automated','Semi-automated'),('automated','Automated')],default='manual',max_length=24)),
        migrations.AlterField(model_name='controltest',name='frequency',field=models.CharField(choices=[('on_demand','On demand'),('monthly','Monthly'),('quarterly','Quarterly'),('semiannual','Semiannual'),('annual','Annual')],default='on_demand',max_length=20)),
        migrations.AlterField(model_name='controltestrun',name='result',field=models.CharField(choices=[('pass','Pass'),('fail','Fail'),('partial','Partial'),('not_applicable','Not applicable'),('error','Error')],max_length=20)),
        migrations.AddIndex(model_name='controltest',index=models.Index(fields=['control_implementation','is_active'],name='controls_co_control_7d9c1b_idx')),
        migrations.AddIndex(model_name='controltestrun',index=models.Index(fields=['control_test','executed_at'],name='controls_co_control_578fe6_idx')),
        migrations.AddIndex(model_name='controltestrun',index=models.Index(fields=['result','executed_at'],name='controls_co_result_6e1e9f_idx')),
    ]
