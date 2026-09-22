from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('internal_audits','0001_initial')]
    operations=[
        migrations.AlterField(model_name='auditengagement',name='audit_type',field=models.CharField(choices=[('internal','Internal'),('framework','Framework'),('control','Control'),('process','Process'),('follow_up','Follow-up')],default='internal',max_length=20)),
        migrations.AlterField(model_name='auditengagement',name='status',field=models.CharField(choices=[('draft','Draft'),('planned','Planned'),('in_progress','In progress'),('review','Review'),('completed','Completed'),('cancelled','Cancelled')],default='draft',max_length=20)),
        migrations.AlterField(model_name='auditplan',name='status',field=models.CharField(choices=[('draft','Draft'),('approved','Approved'),('active','Active'),('closed','Closed')],default='draft',max_length=20)),
        migrations.AlterField(model_name='workpaper',name='result',field=models.CharField(choices=[('not_tested','Not tested'),('pass','Pass'),('fail','Fail'),('partial','Partial'),('not_applicable','Not applicable')],default='not_tested',max_length=20)),
        migrations.AlterField(model_name='workpaper',name='status',field=models.CharField(choices=[('draft','Draft'),('ready','Ready for review'),('reviewed','Reviewed')],default='draft',max_length=20)),
        migrations.AddIndex(model_name='auditengagement',index=models.Index(fields=['tenant','organization_unit','status'],name='internal_au_tenant__955cca_idx')),
        migrations.AddIndex(model_name='auditengagement',index=models.Index(fields=['tenant','lead_auditor','start_date'],name='internal_au_tenant__f1e3f8_idx')),
        migrations.AddIndex(model_name='auditplan',index=models.Index(fields=['tenant','organization_unit','status'],name='internal_au_tenant__7fd37b_idx')),
        migrations.AddIndex(model_name='auditplan',index=models.Index(fields=['tenant','period_start','period_end'],name='internal_au_tenant__0511ba_idx')),
        migrations.AddIndex(model_name='workpaper',index=models.Index(fields=['engagement','status'],name='internal_au_engagem_dc941f_idx')),
        migrations.AddIndex(model_name='workpaper',index=models.Index(fields=['engagement','result'],name='internal_au_engagem_928e5e_idx')),
    ]
