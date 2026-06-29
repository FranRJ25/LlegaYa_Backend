import re
from rest_framework import serializers


def validar_solo_letras(value):
    if not re.match(r'^[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s]+$', value):
        raise serializers.ValidationError('Solo se permiten letras y espacios.')
    return value


def validar_telefono_peruano(value):
    if value and not re.match(r'^\d{9}$', value):
        raise serializers.ValidationError('El celular debe tener exactamente 9 dígitos.')
    return value


def validar_dni(value):
    if value and not re.match(r'^\d{8}$', value):
        raise serializers.ValidationError('El DNI debe tener exactamente 8 dígitos.')
    return value


def validar_password(value):
    if len(value) < 6:
        raise serializers.ValidationError('Mínimo 6 caracteres.')
    if len(value) > 35:
        raise serializers.ValidationError('Máximo 35 caracteres.')
    if not re.search(r'\d', value):
        raise serializers.ValidationError('Debe contener al menos un número.')
    return value

def validar_ruc(value):
    if value and not re.match(r'^\d{11}$', value):
        raise serializers.ValidationError('El RUC debe tener exactamente 11 dígitos.')
    return value

def validar_descripcion(value):
    if len(value) < 8:
        raise serializers.ValidationError('Mínimo 8 caracteres.')
    if len(value) > 200:
        raise serializers.ValidationError('Máximo 200 caracteres.')
    return value

def validar_direccion(value):
    if len(value) < 5:
        raise serializers.ValidationError('Mínimo 5 caracteres.')
    if len(value) > 255:
        raise serializers.ValidationError('Máximo 255 caracteres.')
    return value    