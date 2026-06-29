from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .validators import validar_solo_letras, validar_telefono_peruano, validar_dni, validar_password, validar_ruc, validar_descripcion, validar_direccion
from .models import Usuario, Rol, Negocio, Producto, Pedido, DetallePedido, HistorialCambioProducto, PerfilRepartidor, Pago

class RegisterRepartidorSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=100, validators=[validar_solo_letras])
    apellidos = serializers.CharField(max_length=100, validators=[validar_solo_letras])
    email = serializers.EmailField()
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, validators=[validar_telefono_peruano])
    password = serializers.CharField(write_only=True, min_length=6, validators=[validar_password])
    dni = serializers.CharField(max_length=8, required=False, allow_blank=True, validators=[validar_dni])
    vehiculo = serializers.ChoiceField(choices=PerfilRepartidor.VEHICULOS, default='moto')
    zona_cobertura = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo ya está registrado en el sistema.")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            try:
                rol_repartidor = Rol.objects.get(nombre='repartidor')
            except Rol.DoesNotExist:
                raise serializers.ValidationError({"rol": "El rol 'repartidor' no existe en la BD."})

            usuario = Usuario.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password'],
                nombre=validated_data['nombres'],
                apellido=validated_data['apellidos'],
                telefono=validated_data.get('telefono', ''),
                rol=rol_repartidor
            )

            PerfilRepartidor.objects.create(
                usuario=usuario,
                dni=validated_data.get('dni', ''),
                vehiculo=validated_data.get('vehiculo', 'moto'),
                zona_cobertura=validated_data.get('zona_cobertura', '')
            )
        return usuario

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
    password   = serializers.CharField(write_only=True, min_length=6, max_length=35, validators=[validar_password])
    rol_nombre = serializers.CharField(write_only=True, required=False, default='cliente')
    nombre     = serializers.CharField(max_length=100, validators=[validar_solo_letras])
    apellido   = serializers.CharField(max_length=100, validators=[validar_solo_letras])
    email      = serializers.EmailField(max_length=254)
    telefono   = serializers.CharField(required=False, allow_blank=True, validators=[validar_telefono_peruano])

    class Meta:
        model  = Usuario
        fields = ['email', 'nombre', 'apellido', 'telefono', 'password',
                  'rol_nombre']
        
    def validate_email(self, value):  # ← esto faltaba
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo ya está registrado.")
        return value

    def create(self, validated_data):
        password   = validated_data.pop('password')
        rol_nombre = validated_data.pop('rol_nombre', 'cliente')

        user = Usuario(**validated_data)
        user.set_password(password)

        try:
            user.rol = Rol.objects.get(nombre=rol_nombre)
        except Rol.DoesNotExist:
            user.rol = Rol.objects.get(nombre='cliente')
        user.save()

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
    ruc          = serializers.CharField(max_length=11, required=False, allow_blank=True)
    razon_social = serializers.CharField(max_length=200, required=False, allow_blank=True)
    nombre       = serializers.CharField(max_length=150)
    descripcion  = serializers.CharField(required=False, allow_blank=True)
    telefono     = serializers.CharField(max_length=9, required=False, allow_blank=True)
    direccion    = serializers.CharField(max_length=255)

    def validate_ruc(self, value):
        return validar_ruc(value)

    def validate_descripcion(self, value):
        if not value:
            return value
        return validar_descripcion(value)

    def validate_telefono(self, value):
        return validar_telefono_peruano(value)

    def validate_direccion(self, value):
        return validar_direccion(value)

    class Meta:
        model  = Negocio
        fields = [
            'nombre', 'descripcion', 'direccion', 'categoria',
            'ruc', 'razon_social', 'telefono',
            'hora_apertura', 'hora_cierre', 'dias_atencion',
        ]


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