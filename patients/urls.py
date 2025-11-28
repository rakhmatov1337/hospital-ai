from django.urls import path

from .views import PatientHomeView


app_name = 'patients'

urlpatterns = [
    path('home/', PatientHomeView.as_view(), name='home'),
]


