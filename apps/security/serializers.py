from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Usuario, Rol, Negocio, Producto, Pedido, DetallePedido


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Rol
        fields = ['id', 'nombre']


class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolSerializer(read_only=True)

    class Meta:
        model  = Usuario
        fields = ['id', 'email', 'nombre', 'apellido', 'telefono', 'rol', 'activo', 'created_at', 'foto']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    rol_id   = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(), source='rol', write_only=True, required=False
    )

    class Meta:
        model  = Usuario
        fields = ['email', 'nombre', 'apellido', 'telefono', 'password', 'rol_id']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = Usuario(**validated_data)
        user.set_password(password)
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
        fields = ['id', 'propietario', 'nombre', 'descripcion', 'direccion', 'categoria', 'activo', 'created_at']


class NegocioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Negocio
        fields = ['nombre', 'descripcion', 'direccion', 'categoria']

    def create(self, validated_data):
        return Negocio.objects.create(**validated_data)


class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Producto
        fields = ['id', 'negocio', 'nombre', 'descripcion', 'precio', 'disponible']


class DetallePedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DetallePedido
        fields = ['id', 'producto', 'cantidad', 'precio_unitario']


class PedidoSerializer(serializers.ModelSerializer):
    detalles   = DetallePedidoSerializer(many=True, read_only=True)
    cliente    = UsuarioSerializer(read_only=True)
    repartidor = UsuarioSerializer(read_only=True)

    class Meta:
        model  = Pedido
        fields = ['id', 'cliente', 'negocio', 'repartidor', 'estado', 'total', 'direccion_entrega', 'detalles', 'created_at']