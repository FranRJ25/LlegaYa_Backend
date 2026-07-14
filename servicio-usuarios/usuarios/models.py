import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UsuarioManager


class Rol(models.Model):
    ADMIN = "admin"
    CLIENTE = "cliente"
    REPARTIDOR = "repartidor"

    nombre = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = "rol"

    def __str__(self):
        return self.nombre


class Usuario(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)
    activo = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    foto = models.ImageField(upload_to="fotos_perfil/", null=True, blank=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        db_table = "usuario"

    def __str__(self):
        return self.email


class PasswordResetToken(models.Model):
    user = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        db_table = "password_reset_token"

    def is_valid(self):
        expiry = self.created_at + timedelta(minutes=15)
        return not self.used and timezone.now() < expiry
