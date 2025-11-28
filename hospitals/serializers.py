from rest_framework import serializers

from .models import Hospital
from patients.serializers import PatientDetailSerializer


class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = ['id', 'name', 'description', 'administrator', 'created_at', 'updated_at']


class DashboardAlertSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    label = serializers.CharField()
    message = serializers.CharField()
    priority_level = serializers.CharField(required=False, allow_null=True)


class DashboardTaskSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    task = serializers.CharField()
    status = serializers.CharField()


class RecentPatientSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    status = serializers.CharField()
    surgery_name = serializers.CharField(required=False, allow_null=True)
    priority_level = serializers.CharField(required=False, allow_null=True)
    admitted_at = serializers.DateTimeField()


class HospitalDashboardSerializer(serializers.Serializer):
    total_patients = serializers.IntegerField()
    recovery_patients = serializers.IntegerField()
    discharged_patients = serializers.IntegerField()
    high_priority_patients = serializers.IntegerField()
    recent_patients = RecentPatientSerializer(many=True)


class HospitalProfileSerializer(serializers.ModelSerializer):
    patients = PatientDetailSerializer(many=True, read_only=True)
    patients_count = serializers.IntegerField(source='patients.count', read_only=True)

    class Meta:
        model = Hospital
        fields = [
            'id',
            'name',
            'description',
            'administrator',
            'created_at',
            'updated_at',
            'patients_count',
            'patients',
        ]
        read_only_fields = fields


class HospitalAIChatSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=1000,
        help_text='Free-form question for the AI medical assistant.',
    )
    patient_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text='Optional patient ID to ground the answer in a specific patient.',
    )

