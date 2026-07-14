from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Rol, Usuario
from .validators import validar_password, validar_solo_letras, validar_telefono_peruano


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.CharField(source="rol.nombre", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "apellido", "telefono", "rol", "foto", "activo", "created_at"]
        read_only_fields = ["id", "activo", "created_at"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validar_password])
    rol = serializers.ChoiceField(choices=[Rol.CLIENTE, Rol.ADMIN, Rol.REPARTIDOR], default=Rol.CLIENTE, write_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "password", "nombre", "apellido", "telefono", "rol"]

    def validate_nombre(self, valor):
        validar_solo_letras(valor)
        return valor

    def validate_telefono(self, valor):
        if valor:
            validar_telefono_peruano(valor)
        return valor

    def create(self, validated_data):
        nombre_rol = validated_data.pop("rol", Rol.CLIENTE)
        rol_obj, _ = Rol.objects.get_or_create(nombre=nombre_rol)
        password = validated_data.pop("password")
        usuario = Usuario(rol=rol_obj, **validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = Usuario.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["nombre"] = user.nombre
        token["rol"] = user.rol.nombre if user.rol else ""
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = UsuarioSerializer(self.user).data
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(validators=[validar_password])
