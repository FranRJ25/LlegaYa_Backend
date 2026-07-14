import re

from django.core.exceptions import ValidationError


def validar_ruc(valor):
    if valor and not re.match(r"^\d{11}$", valor):
        raise ValidationError("El RUC debe tener 11 digitos.")


def validar_telefono_peruano(valor):
    if valor and not re.match(r"^9\d{8}$", valor):
        raise ValidationError("El telefono debe tener 9 digitos y empezar con 9.")


def validar_descripcion(valor):
    if valor and len(valor) > 1000:
        raise ValidationError("La descripcion no puede superar los 1000 caracteres.")


def validar_direccion(valor):
    if not valor or len(valor.strip()) < 5:
        raise ValidationError("La direccion debe tener al menos 5 caracteres.")
