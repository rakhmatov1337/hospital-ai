from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomTokenObtainPairView, PatientTokenObtainPairView


app_name = 'accounts'

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('patients/login/', PatientTokenObtainPairView.as_view(), name='patient-login'),
]

