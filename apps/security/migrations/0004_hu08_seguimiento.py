from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0003_negocio_dias_atencion_negocio_hora_apertura_and_more'),
    ]

    operations = [
        # Campos nuevos en Pedido
        migrations.AddField(
            model_name='pedido',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='lat_entrega',
            field=models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='lng_entrega',
            field=models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True),
        ),
        # Nuevo modelo: HistorialEstadoPedido
        migrations.CreateModel(
            name='HistorialEstadoPedido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado_anterior', models.CharField(blank=True, default='', max_length=20)),
                ('estado_nuevo', models.CharField(max_length=20)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('comentario', models.CharField(blank=True, default='', max_length=255)),
                ('cambiado_por', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='cambios_estado_pedido',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('pedido', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='historial_estados',
                    to='security.pedido',
                )),
            ],
            options={
                'db_table': 'historial_estado_pedido',
                'ordering': ['-fecha'],
            },
        ),
    ]