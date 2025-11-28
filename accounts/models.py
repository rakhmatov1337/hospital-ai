from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        HOSPITAL = 'hospital', 'Hospital'
        PATIENT = 'patient', 'Patient'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.ADMIN,
        help_text='Determines the permission scope for the user.',
    )

    def __str__(self) -> str:
        base = super().__str__()
        return f'{base} ({self.get_role_display()})'
