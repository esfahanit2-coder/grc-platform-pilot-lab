from django.db import migrations, models
from pgvector.django import VectorExtension, VectorField

class Migration(migrations.Migration):
    dependencies=[("ai_gateway","0001_initial")]
    operations=[
        VectorExtension(),
        migrations.AddField(model_name="knowledgechunk",name="embedding",field=VectorField(blank=True,null=True)),
        migrations.AddField(model_name="knowledgechunk",name="embedding_model",field=models.CharField(blank=True,max_length=160)),
        migrations.AddField(model_name="knowledgechunk",name="embedding_dimensions",field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="knowledgechunk",name="embedded_at",field=models.DateTimeField(blank=True,null=True)),
    ]
