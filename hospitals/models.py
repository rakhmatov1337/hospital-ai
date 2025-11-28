from django.conf import settings
from django.db import models


class Hospital(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hospital_profile',
        blank=True,
        null=True,
        help_text='Optional link to the hospital admin user account.',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    administrator = models.CharField(
        max_length=255,
        help_text='Primary administrator contact for the hospital.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class HospitalChatMessage(models.Model):
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name='chat_messages',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hospital_chat_messages',
    )
    question = models.TextField()
    answer = models.TextField()
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        related_name='chat_messages',
        blank=True,
        null=True,
        help_text='Patient mentioned in this conversation, if any.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hospital', 'user', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.hospital.name} - {self.question[:50]}...'
