from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_token_media_from_ipfs'),
    ]

    operations = [
        migrations.AlterField(
            model_name='token',
            name='tx_hash',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
