from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    CustomTokenObtainPairSerializer,
    PatientTokenObtainPairSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = (AllowAny,)


class PatientTokenObtainPairView(TokenObtainPairView):
    serializer_class = PatientTokenObtainPairSerializer
    permission_classes = (AllowAny,)
