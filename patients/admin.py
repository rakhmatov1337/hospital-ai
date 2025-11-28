from django.contrib import admin

from .models import MedicalRecord, Patient, PatientCarePlan, RecordText


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'hospital', 'status', 'surgery')
    list_filter = ('status', 'hospital')
    search_fields = ('full_name', 'assigned_doctor', 'ward')


@admin.register(RecordText)
class RecordTextAdmin(admin.ModelAdmin):
    list_display = ('patient', 'date')
    list_filter = ('date',)


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('record_title', 'patient', 'record_text')


@admin.register(PatientCarePlan)
class PatientCarePlanAdmin(admin.ModelAdmin):
    list_display = ('patient', 'updated_at')
    search_fields = ('patient__full_name',)
