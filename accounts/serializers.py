from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

try:
    TokenObtainPairSerializer = import_string(
        'rest_framework_simplejwt.serializers.TokenObtainPairSerializer'
    )
except ImportError as exc:  # pragma: no cover - configuration safeguard
    raise ImproperlyConfigured(
        'djangorestframework-simplejwt must be installed to use authentication serializers.'
    ) from exc


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Adds basic user context to the token response and embeds the
    role into the JWT payload so clients can perform quick checks.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': self.user.role,
        }
        return data


class HospitalTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    default_error_messages = {
        'not_hospital': 'Only hospital accounts can access this endpoint.',
    }

    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role != self.user.Roles.HOSPITAL:
            self.fail('not_hospital')
        return data


class PatientTokenObtainPairSerializer(CustomTokenObtainPairSerializer):
    default_error_messages = {
        'not_patient': 'Only patient accounts can access this endpoint.',
    }

    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role != self.user.Roles.PATIENT:
            self.fail('not_patient')
        return data

