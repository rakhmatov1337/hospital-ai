from django.urls import re_path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    HospitalAIChatView,
    HospitalActivityPlanViewSet,
    HospitalDashboardView,
    HospitalDietPlanViewSet,
    HospitalDietTypesView,
    HospitalMedicationViewSet,
    HospitalPatientViewSet,
    HospitalProfileView,
    HospitalSurgeryTypesView,
    HospitalSurgeryViewSet,
    HospitalTokenObtainPairView,
)

app_name = 'hospitals'

router = DefaultRouter()
router.trailing_slash = '/?'
router.register('patients', HospitalPatientViewSet, basename='hospital-patients')
router.register('surgeries', HospitalSurgeryViewSet, basename='hospital-surgeries')
router.register('medications', HospitalMedicationViewSet, basename='hospital-medications')
router.register('diet-plans', HospitalDietPlanViewSet, basename='hospital-diet-plans')
router.register('activities', HospitalActivityPlanViewSet, basename='hospital-activity-plans')

urlpatterns = [
    re_path(r'^auth/login/?$', HospitalTokenObtainPairView.as_view(), name='login'),
    re_path(r'^auth/refresh/?$', TokenRefreshView.as_view(), name='refresh'),
    re_path(r'^auth/me/?$', HospitalProfileView.as_view(), name='me'),
    re_path(r'^dashboard/?$', HospitalDashboardView.as_view(), name='dashboard'),
    re_path(r'^ai-chat/?$', HospitalAIChatView.as_view(), name='ai-chat'),
    re_path(r'^diet-types/?$', HospitalDietTypesView.as_view(), name='diet-types'),
    re_path(r'^surgery-types/?$', HospitalSurgeryTypesView.as_view(), name='surgery-types'),
]

urlpatterns += router.urls

