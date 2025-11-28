from django.urls import re_path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    HospitalDashboardView,
    HospitalMedicationViewSet,
    HospitalPatientViewSet,
    HospitalProfileView,
    HospitalSurgeryViewSet,
    HospitalTokenObtainPairView,
)

app_name = 'hospitals'

router = DefaultRouter()
router.trailing_slash = '/?'
router.register('patients', HospitalPatientViewSet, basename='hospital-patients')
router.register('surgeries', HospitalSurgeryViewSet, basename='hospital-surgeries')
router.register('medications', HospitalMedicationViewSet, basename='hospital-medications')

urlpatterns = [
    re_path(r'^auth/login/?$', HospitalTokenObtainPairView.as_view(), name='login'),
    re_path(r'^auth/refresh/?$', TokenRefreshView.as_view(), name='refresh'),
    re_path(r'^auth/me/?$', HospitalProfileView.as_view(), name='me'),
    re_path(r'^dashboard/?$', HospitalDashboardView.as_view(), name='dashboard'),
]

urlpatterns += router.urls

