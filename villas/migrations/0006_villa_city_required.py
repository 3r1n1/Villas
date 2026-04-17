from django.db import migrations, models


def fill_empty_city(apps, schema_editor):
    Villa = apps.get_model("villas", "Villa")
    Villa.objects.filter(city="").update(city="Unspecified")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("villas", "0005_villa_bathroom_count_villa_bedroom_count_villa_city_and_more"),
    ]

    operations = [
        migrations.RunPython(fill_empty_city, noop_reverse),
        migrations.AlterField(
            model_name="villa",
            name="city",
            field=models.CharField(
                help_text="City (required for listings and search).",
                max_length=120,
            ),
        ),
    ]
