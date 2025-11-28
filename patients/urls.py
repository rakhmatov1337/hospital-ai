from django.urls import path, re_path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ActivitySafetyCheckView,
    PatientAIChatView,
    PatientActivitiesView,
    PatientHomeView,
    PatientMeView,
    PatientMedicationsView,
    PatientDietPlanView,
    PatientTasksUpdateView,
    PatientTokenObtainPairView,
)


app_name = 'patients'

urlpatterns = [
    re_path(r'^home/?$', PatientHomeView.as_view(), name='home'),
    re_path(r'^login/?$', PatientTokenObtainPairView.as_view(), name='login'),
    re_path(r'^refresh/?$', TokenRefreshView.as_view(), name='refresh'),
    re_path(r'^me/?$', PatientMeView.as_view(), name='me'),
    re_path(r'^medications/?$', PatientMedicationsView.as_view(), name='medications'),
    re_path(r'^diet-plan/?$', PatientDietPlanView.as_view(), name='diet-plan'),
    re_path(r'^activities/?$', PatientActivitiesView.as_view(), name='activities'),
    re_path(r'^activities/ask-ai/?$', ActivitySafetyCheckView.as_view(), name='activities-ask-ai'),
    re_path(r'^ai-chat/?$', PatientAIChatView.as_view(), name='ai-chat'),
    re_path(r'^home/tasks/(?P<task_id>\d+)/?$', PatientTasksUpdateView.as_view(), name='home-tasks-update'),
]


