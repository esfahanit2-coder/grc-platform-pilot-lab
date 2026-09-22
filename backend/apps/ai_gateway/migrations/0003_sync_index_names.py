from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('ai_gateway','0002_semantic_rag_pgvector')]
    operations=[
        migrations.RenameIndex(model_name='aiinteraction',old_name='ai_gateway_a_tenant__453503_idx',new_name='ai_gateway__tenant__c1544e_idx'),
        migrations.RenameIndex(model_name='aiinteraction',old_name='ai_gateway_a_tenant__c4c099_idx',new_name='ai_gateway__tenant__e11946_idx'),
        migrations.RenameIndex(model_name='aiproviderconfig',old_name='ai_gateway_a_tenant__92ad0d_idx',new_name='ai_gateway__tenant__a399f5_idx'),
        migrations.RenameIndex(model_name='aisuggestion',old_name='ai_gateway_a_tenant__51bd42_idx',new_name='ai_gateway__tenant__118f96_idx'),
        migrations.RenameIndex(model_name='aisuggestion',old_name='ai_gateway_a_tenant__777be6_idx',new_name='ai_gateway__tenant__1232a7_idx'),
        migrations.RenameIndex(model_name='knowledgechunk',old_name='ai_gateway_k_tenant__331fac_idx',new_name='ai_gateway__tenant__79dc6b_idx'),
        migrations.RenameIndex(model_name='knowledgechunk',old_name='ai_gateway_k_tenant__ca264b_idx',new_name='ai_gateway__tenant__9bc311_idx'),
    ]
