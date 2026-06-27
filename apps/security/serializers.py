from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .models import Usuario, Rol, Negocio, Producto, Pedido, DetallePedido, HistorialCambioProducto, PerfilRepartidor, Pago

# --- NUEVO SERIALIZADOR PARA REPARTIDOR ---
class RegisterRepartidorSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=100)
    apellidos = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    celular = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=6)
    
    dni = serializers.CharField(max_length=8, required=False, allow_blank=True)
    vehiculo = serializers.ChoiceField(choices=PerfilRepartidor.VEHICULOS, default='moto')
    zona_cobertura = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo ya está registrado en el sistema.")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            try:
                # Buscamos el rol por nombre (más seguro que por ID)
                rol_repartidor = Rol.objects.get(nombre='repartidor')
            except Rol.DoesNotExist:
                raise serializers.ValidationError({"rol": "El rol 'repartidor' no existe en la BD."})

            usuario = Usuario.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                nombre=validated_data['nombres'],
                apellido=validated_data['apellidos'],
                telefono=validated_data.get('celular', ''),
                rol=rol_repartidor
            )

            PerfilRepartidor.objects.create(
                usuario=usuario,
                dni=validated_data.get('dni', ''),
                vehiculo=validated_data.get('vehiculo', 'moto'),
                zona_cobertura=validated_data.get('zona_cobertura', '')
            )
        return usuario


# --- EL RESTO DE TUS SERIALIZADORES (INTACTOS) ---

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Rol
        fields = ['id', 'nombre']


class PerfilRepartidorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PerfilRepartidor
        fields = ['id', 'dni', 'vehiculo', 'zona_cobertura', 'disponible', 'created_at']


class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)

    class Meta:
        model  = Usuario
        fields = ['id', 'email', 'nombre', 'apellido', 'telefono', 'rol', 'activo', 'created_at', 'foto']


class RegisterSerializer(serializers.ModelSerializer):
    password       = serializers.CharField(write_only=True, min_length=6)
    rol_nombre     = serializers.CharField(write_only=True, required=False, default='cliente')
    dni            = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehiculo       = serializers.CharField(write_only=True, required=False, allow_blank=True)
    zona_cobertura = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model  = Usuario
        fields = ['email', 'nombre', 'apellido', 'telefono', 'password',
                  'rol_nombre', 'dni', 'vehiculo', 'zona_cobertura']

    def create(self, validated_data):
        password       = validated_data.pop('password')
        rol_nombre     = validated_data.pop('rol_nombre', 'cliente')
        dni            = validated_data.pop('dni', '')
        vehiculo       = validated_data.pop('vehiculo', 'moto')
        zona_cobertura = validated_data.pop('zona_cobertura', '')

        user = Usuario(**validated_data)
        user.set_password(password)

        try:
            user.rol = Rol.objects.get(nombre=rol_nombre)
        except Rol.DoesNotExist:
            user.rol = Rol.objects.get(nombre='cliente')
        user.save()

        if rol_nombre == 'repartidor':
            PerfilRepartidor.objects.create(
                usuario        = user,
                dni            = dni,
                vehiculo       = vehiculo,
                zona_cobertura = zona_cobertura,
            )

        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email']  = user.email
        token['nombre'] = user.nombre
        token['rol']    = user.rol.nombre if user.rol else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = {
            'id':      self.user.id,
            'email':   self.user.email,
            'nombre':  self.user.nombre,
            'apellido': self.user.apellido,
            'rol':     self.user.rol.nombre if self.user.rol else None,
        }
        return data


class NegocioSerializer(serializers.ModelSerializer):
    propietario = UsuarioSerializer(read_only=True)

    class Meta:
        model  = Negocio
        fields = [
            'id', 'propietario', 'nombre', 'descripcion',
            'direccion', 'categoria', 'activo', 'created_at',
            'ruc', 'razon_social', 'telefono',
            'hora_apertura', 'hora_cierre', 'dias_atencion',
        ]


class NegocioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Negocio
        fields = [
            'nombre', 'descripcion', 'direccion', 'categoria',
            'ruc', 'razon_social', 'telefono',
            'hora_apertura', 'hora_cierre', 'dias_atencion',
        ]

    def create(self, validated_data):
        return Negocio.objects.create(**validated_data)


class ProductoSerializer(serializers.ModelSerializer):
    categoria_label = serializers.SerializerMethodField()

    class Meta:
        model  = Producto
        fields = [
            'id', 'negocio', 'nombre', 'descripcion', 'precio', 'categoria', 'categoria_label', 'disponible', 'created_at', 'updated_at'
        ]
        read_only_fields = ['negocio', 'created_at', 'updated_at']

    def get_categoria_label(self, obj):
        return obj.get_categoria_display()
    
class HistorialCambioSerializer(serializers.ModelSerializer):
    tipo_cambio_label = serializers.SerializerMethodField()
    usuario_nombre    = serializers.SerializerMethodField()
    producto_nombre   = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model  = HistorialCambioProducto
        fields = [
            'id', 'producto', 'producto_nombre',
            'usuario', 'usuario_nombre',
            'tipo_cambio', 'tipo_cambio_label',
            'valor_anterior', 'valor_nuevo', 'comentario', 'fecha'
        ]

    def get_tipo_cambio_label(self, obj):
        return obj.get_tipo_cambio_display()

    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return f'{obj.usuario.nombre} {obj.usuario.apellido}'.strip()
        return 'Sistema'


class DetallePedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DetallePedido
        fields = ['id', 'producto', 'cantidad', 'precio_unitario']

class PagoSerializer(serializers.ModelSerializer):
    numero_transaccion = serializers.UUIDField(read_only=True)
    fecha              = serializers.DateTimeField(read_only=True)

    class Meta:
        model  = Pago
        fields = ['id', 'pedido', 'monto', 'metodo', 'numero_transaccion', 'fecha']
        read_only_fields = ['numero_transaccion', 'fecha']        

class PedidoSerializer(serializers.ModelSerializer):
    detalles      = DetallePedidoSerializer(many=True, read_only=True)
    cliente       = UsuarioSerializer(read_only=True)
    repartidor    = UsuarioSerializer(read_only=True)
    estado_label  = serializers.SerializerMethodField()
    negocio_info  = serializers.SerializerMethodField()

    class Meta:
        model  = Pedido
        fields = [
            'id', 'cliente', 'negocio', 'negocio_info', 'repartidor',
            'estado', 'estado_label', 'total', 'direccion_entrega',
            'motivo_cancelacion',   # ← nuevo
            'detalles', 'created_at'
        ]

    def get_estado_label(self, obj):
        labels = {
            'pendiente':  'Pendiente',
            'confirmado': 'Confirmado',
            'en_camino':  'En camino',
            'entregado':  'Entregado',
            'cancelado':  'Cancelado',
            'completado': 'Completado',  # ← nuevo
        }
        return labels.get(obj.estado, obj.estado)

    def get_negocio_info(self, obj):
        n = obj.negocio
        return {
            'id':        n.id,
            'nombre':    n.nombre,
            'categoria': n.categoria,
            'direccion': n.direccion,
            'telefono':  n.telefono,
        }
    
class PedidoConPagoSerializer(PedidoSerializer):
    pago = serializers.SerializerMethodField()

    class Meta(PedidoSerializer.Meta):
        fields = PedidoSerializer.Meta.fields + ['pago']

    def get_pago(self, obj):
        try:
            return PagoSerializer(obj.pago).data
        except Pago.DoesNotExist:
            return None    
    
class RepartidorSerializer(serializers.ModelSerializer):
    perfil_repartidor = PerfilRepartidorSerializer(read_only=True)
    rol = RolSerializer(read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'email', 'nombre', 'apellido', 'telefono',
            'rol', 'activo', 'created_at', 'perfil_repartidor'
        ]