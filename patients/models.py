from django.conf import settings
from django.db import models


class Patient(models.Model):
    class GenderChoices(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    class StatusChoices(models.TextChoices):
        IN_RECOVERY = 'in_recovery', 'In Recovery'
        DISCHARGED = 'discharged', 'Discharged'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_profile',
        blank=True,
        null=True,
        help_text='Optional link to the patient user account.',
    )
    hospital = models.ForeignKey(
        'hospitals.Hospital',
        on_delete=models.SET_NULL,
        related_name='patients',
        blank=True,
        null=True,
    )
    full_name = models.CharField(max_length=255)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=GenderChoices.choices)
    phone = models.CharField(max_length=50, unique=True)
    assigned_doctor = models.CharField(max_length=255)
    admitted_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.IN_RECOVERY,
    )
    surgery = models.ForeignKey(
        'surgeries.Surgery',
        on_delete=models.SET_NULL,
        related_name='patients',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['full_name']

    def __str__(self) -> str:
        return self.full_name


class RecordText(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='record_texts',
    )
    text = models.TextField()
    date = models.DateField()

    class Meta:
        ordering = ['-date']

    def __str__(self) -> str:
        return f'{self.patient.full_name} - {self.date}'


class MedicalRecord(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='medical_records',
    )
    record_title = models.CharField(max_length=255)
    record_text = models.ForeignKey(
        RecordText,
        on_delete=models.CASCADE,
        related_name='medical_records',
    )

    class Meta:
        ordering = ['-record_text__date']

    def __str__(self) -> str:
        return f'{self.record_title} ({self.patient.full_name})'


class PatientCarePlan(models.Model):
    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        related_name='care_summary',
    )
    care_plan = models.JSONField(default=dict, blank=True)
    diet_plan = models.JSONField(default=dict, blank=True)
    activities = models.JSONField(default=dict, blank=True)
    ai_insights = models.JSONField(default=dict, blank=True)
    today_tasks = models.JSONField(default=list, blank=True, help_text='List of today\'s tasks with completion status')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'Care Plan for {self.patient.full_name}'


class Task(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    label = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        return f'{self.label} ({self.patient.full_name})'
