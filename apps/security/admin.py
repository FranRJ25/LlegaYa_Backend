from django.contrib import admin
from .models import Negocio


@admin.register(Negocio)
class NegocioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'comision_porcentaje', 'activo')
    search_fields = ('nombre',)
