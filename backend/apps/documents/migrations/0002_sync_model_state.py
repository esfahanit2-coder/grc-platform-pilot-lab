from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('documents','0001_initial')]
    operations=[
        migrations.AlterModelOptions(name='documentapproval',options={'ordering':['approval_order','created_at']}),
        migrations.AlterField(model_name='document',name='document_type',field=models.CharField(choices=[('policy','Policy'),('procedure','Procedure'),('standard','Standard'),('guideline','Guideline'),('plan','Plan'),('charter','Charter'),('form','Form'),('record','Record'),('report','Report'),('minutes','Minutes')],max_length=24)),
        migrations.AlterField(model_name='document',name='status',field=models.CharField(choices=[('draft','Draft'),('review','In review'),('approved','Approved'),('published','Published'),('deprecated','Deprecated')],default='draft',max_length=20)),
        migrations.AlterField(model_name='documentapproval',name='decision',field=models.CharField(choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected'),('changes_requested','Changes requested')],default='pending',max_length=24)),
        migrations.AlterField(model_name='documentversion',name='status',field=models.CharField(choices=[('draft','Draft'),('review','Review'),('approved','Approved'),('published','Published'),('superseded','Superseded')],default='draft',max_length=20)),
        migrations.AlterField(model_name='reporttemplate',name='template_type',field=models.CharField(choices=[('rtp','RTP'),('soa','SoA'),('audit','Audit report'),('assessment','Assessment report'),('executive','Executive report'),('custom','Custom')],max_length=24)),
        migrations.AddIndex(model_name='document',index=models.Index(fields=['tenant','organization_unit','status'],name='documents_d_tenant__d3b8cf_idx')),
        migrations.AddIndex(model_name='document',index=models.Index(fields=['tenant','review_date'],name='documents_d_tenant__228023_idx')),
        migrations.AddIndex(model_name='documentlink',index=models.Index(fields=['tenant','object_type','object_id'],name='documents_d_tenant__c8add8_idx')),
        migrations.AddIndex(model_name='documentversion',index=models.Index(fields=['document','status'],name='documents_d_documen_4dd74e_idx')),
    ]
