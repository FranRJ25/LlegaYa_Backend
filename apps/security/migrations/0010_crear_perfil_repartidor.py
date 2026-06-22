from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0009_remove_usuario_zona'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilRepartidor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dni', models.CharField(blank=True, max_length=8)),
                ('vehiculo', models.CharField(choices=[('moto', 'Moto'), ('bicicleta', 'Bicicleta'), ('a_pie', 'A pie'), ('auto', 'Auto')], default='moto', max_length=20)),
                ('zona_cobertura', models.CharField(blank=True, max_length=255)),
                ('disponible', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='perfil_repartidor',
                    to='security.usuario',
                )),
            ],
            options={
                'db_table': 'perfil_repartidor',
            },
        ),
    ]