import re

from django.core.exceptions import ValidationError


def validar_solo_letras(valor):
    if not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$", valor or ""):
        raise ValidationError("Solo se permiten letras y espacios.")


def validar_telefono_peruano(valor):
    if not re.match(r"^9\d{8}$", valor or ""):
        raise ValidationError("El telefono debe tener 9 digitos y empezar con 9.")


def validar_password(valor):
    if len(valor or "") < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", valor):
        raise ValidationError("La contraseña debe tener al menos una mayuscula.")
    if not re.search(r"\d", valor):
        raise ValidationError("La contraseña debe tener al menos un numero.")
