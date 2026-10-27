from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0003_reviewcorrection"),
    ]

    operations = [
        migrations.DeleteModel(name="ReviewCorrection"),
    ]
