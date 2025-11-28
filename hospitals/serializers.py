from rest_framework import serializers

from .models import Hospital


class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = ['id', 'name', 'description', 'administrator', 'created_at', 'updated_at']


class DashboardAlertSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    label = serializers.CharField()
    message = serializers.CharField()
    severity = serializers.CharField()


class DashboardTaskSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    patient_name = serializers.CharField()
    task = serializers.CharField()
    status = serializers.CharField()


class HospitalDashboardSerializer(serializers.Serializer):
    total_patients = serializers.IntegerField()
    surgeries_today = serializers.IntegerField()
    high_risk_patients = serializers.IntegerField()
    appointments_today = serializers.IntegerField()
    alerts = DashboardAlertSerializer(many=True)
    tasks = DashboardTaskSerializer(many=True)
from rest_framework import serializers

from .models import Hospital
from patients.serializers import PatientDetailSerializer


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

