from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import uuid
from datetime import timedelta
from django.utils import timezone
from django.conf import settings


class Rol(models.Model):
    ROLES = [
        ('admin',       'Administrador'),
        ('cliente',     'Cliente'),
        ('repartidor',  'Repartidor'),
    ]
    nombre = models.CharField(max_length=50, choices=ROLES, unique=True)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    email        = models.EmailField(unique=True)
    nombre       = models.CharField(max_length=100)
    apellido     = models.CharField(max_length=100)
    telefono     = models.CharField(max_length=20, blank=True)
    rol          = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)
    activo       = models.BooleanField(default=True)
    is_active    = models.BooleanField(default=True)  
    is_staff     = models.BooleanField(default=False)  
    created_at   = models.DateTimeField(auto_now_add=True)
    foto         = models.ImageField(upload_to='fotos_perfil/', null=True, blank=True)
    
    objects = UsuarioManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f'{self.email} — {self.rol}'


class Negocio(models.Model):
    CATEGORIAS = [
        ('restaurante', 'Restaurante'),
        ('tienda',      'Tienda'),
        ('farmacia',    'Farmacia'),
        ('otro',        'Otro'),
    ]
    propietario  = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name='negocio'
    )
    nombre       = models.CharField(max_length=150)
    descripcion  = models.TextField(blank=True)
    direccion    = models.CharField(max_length=255)
    categoria    = models.CharField(max_length=50, choices=CATEGORIAS, default='otro')
    activo       = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'negocio'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    negocio      = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='productos')
    nombre       = models.CharField(max_length=150)
    descripcion  = models.TextField(blank=True)
    precio       = models.DecimalField(max_digits=8, decimal_places=2)
    disponible   = models.BooleanField(default=True)

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return f'{self.nombre} — S/ {self.precio}'


class Pedido(models.Model):
    ESTADOS = [
        ('pendiente',   'Pendiente'),
        ('confirmado',  'Confirmado'),
        ('en_camino',   'En camino'),
        ('entregado',   'Entregado'),
        ('cancelado',   'Cancelado'),
    ]
    cliente           = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name='pedidos_como_cliente'
    )
    negocio           = models.ForeignKey(
        Negocio, on_delete=models.PROTECT, related_name='pedidos'
    )
    repartidor        = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pedidos_como_repartidor'
    )
    estado            = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    total             = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    direccion_entrega = models.CharField(max_length=255)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pedido'

    def __str__(self):
        return f'Pedido #{self.id} — {self.estado}'


class DetallePedido(models.Model):
    pedido          = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad        = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        db_table = 'detalle_pedido'

    def __str__(self):
        return f'{self.cantidad}x {self.producto.nombre}'
    

class PasswordResetToken(models.Model):
    user       = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.CASCADE,
                    related_name='reset_tokens'
                 )
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used       = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_token'

    def is_valid(self):
        expiry = self.created_at + timedelta(minutes=15)
        return not self.used and timezone.now() < expiry

    def __str__(self):
        return f"Token de {self.user.email} — {'válido' if self.is_valid() else 'expirado'}"