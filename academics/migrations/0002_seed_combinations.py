from django.db import migrations


def seed_combinations(apps, schema_editor):
    Combination = apps.get_model('academics', 'Combination')
    combinations = [
        {'code': 'PGM', 'name': 'Physics, Geography, Mathematics', 'subjects': 'Physics,Geography,Mathematics'},
        {'code': 'PCM', 'name': 'Physics, Chemistry, Mathematics', 'subjects': 'Physics,Chemistry,Mathematics'},
        {'code': 'PCB', 'name': 'Physics, Chemistry, Biology',     'subjects': 'Physics,Chemistry,Biology'},
        {'code': 'EGM', 'name': 'Economics, Geography, Mathematics','subjects': 'Economics,Geography,Mathematics'},
        {'code': 'HGE', 'name': 'History, Geography, Economics',    'subjects': 'History,Geography,Economics'},
        {'code': 'HKL', 'name': 'History, Kiswahili, Literature',   'subjects': 'History,Kiswahili,Literature'},
    ]
    for c in combinations:
        Combination.objects.get_or_create(code=c['code'], defaults={
            'name': c['name'],
            'subjects': c['subjects'],
        })


def reverse_seed(apps, schema_editor):
    pass  # keep data on reverse


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_combinations, reverse_seed),
    ]
