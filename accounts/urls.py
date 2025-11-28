from django.urls import path, re_path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomTokenObtainPairView


app_name = 'accounts'

urlpatterns = [
    re_path(r'^login/?$', CustomTokenObtainPairView.as_view(), name='login'),
    re_path(r'^refresh/?$', TokenRefreshView.as_view(), name='token_refresh'),
]

