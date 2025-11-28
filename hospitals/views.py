from rest_framework import viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import HospitalTokenObtainPairSerializer
from hospitals.permissions import IsHospitalUser
from hospitals.serializers import (
    HospitalDashboardSerializer,
    HospitalSerializer,
)
from patients.models import Patient
from patients.serializers import (
    PatientDetailSerializer,
    PatientListSerializer,
    PatientWriteSerializer,
)
from surgeries.models import Medication, Surgery
from surgeries.serializers import (
    MedicationSerializer,
    SurgeryDetailSerializer,
    SurgeryListSerializer,
    SurgeryWriteSerializer,
)


class HospitalTokenObtainPairView(TokenObtainPairView):
    serializer_class = HospitalTokenObtainPairSerializer
    permission_classes = (AllowAny,)


class HospitalPatientViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsHospitalUser)

    def get_queryset(self):
        hospital = self._get_hospital()
        if hospital is None:
            # Used during schema generation (swagger_fake_view)
            return Patient.objects.none()
        return (
            Patient.objects.filter(hospital=hospital)
            .select_related('surgery', 'hospital', 'care_summary')
            .prefetch_related(
                'medications',
                'medical_records__record_text',
            )
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return PatientListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return PatientWriteSerializer
        return PatientDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        hospital = self._get_hospital()
        if hospital is not None:
            context['hospital'] = hospital
        return context

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save(hospital=self._get_hospital())

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        if user:
            user.delete()

    def _get_hospital(self):
        if getattr(self, 'swagger_fake_view', False):
            return None
        hospital = getattr(self.request.user, 'hospital_profile', None)
        if hospital is None:
            raise ValidationError('No hospital profile is linked to this account.')
        return hospital


class HospitalMedicationViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsHospitalUser)
    serializer_class = MedicationSerializer

    def get_queryset(self):
        hospital = self._get_hospital()
        if hospital is None:
            return Medication.objects.none()
        return Medication.objects.filter(
            surgery__hospital=hospital,
        ).select_related('surgery', 'patient')

    def perform_create(self, serializer):
        hospital = self._get_hospital()
        surgery = serializer.validated_data.get('surgery')
        if surgery.hospital_id != hospital.id:
            raise ValidationError('Cannot assign medication to surgery of another hospital.')
        serializer.save()

    def _get_hospital(self):
        if getattr(self, 'swagger_fake_view', False):
            return None
        hospital = getattr(self.request.user, 'hospital_profile', None)
        if hospital is None:
            raise ValidationError('No hospital profile is linked to this account.')
        return hospital


class HospitalSurgeryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsHospitalUser)

    def get_queryset(self):
        hospital = self._get_hospital()
        if hospital is None:
            return Surgery.objects.none()
        return (
            Surgery.objects.filter(hospital=hospital)
            .select_related('diet_plan', 'activity_plan')
            .prefetch_related(
                'diet_plan__food_items',
                'diet_plan__meals',
                'activity_plan__activities',
            )
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return SurgeryListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return SurgeryWriteSerializer
        return SurgeryDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        hospital = self._get_hospital()
        if hospital is not None:
            context['hospital'] = hospital
        return context

    def perform_create(self, serializer):
        serializer.save()

    def _get_hospital(self):
        if getattr(self, 'swagger_fake_view', False):
            return None
        hospital = getattr(self.request.user, 'hospital_profile', None)
        if hospital is None:
            raise ValidationError('No hospital profile is linked to this account.')
        return hospital


class HospitalProfileView(APIView):
    permission_classes = (IsAuthenticated, IsHospitalUser)

    def get(self, request):
        hospital = getattr(request.user, 'hospital_profile', None)
        if hospital is None:
            raise NotFound('No hospital profile is linked to this account.')
        serializer = HospitalSerializer(hospital)
        return Response(serializer.data)


class HospitalDashboardView(APIView):
    permission_classes = (IsAuthenticated, IsHospitalUser)

    def get(self, request):
        hospital = getattr(request.user, 'hospital_profile', None)
        if hospital is None:
            raise NotFound('No hospital profile is linked to this account.')

        patients_qs = Patient.objects.filter(hospital=hospital).select_related(
            'surgery', 'care_summary'
        )
        total_patients = patients_qs.count()

        from django.utils import timezone

        today = timezone.localdate()
        surgeries_today = Surgery.objects.filter(
            hospital=hospital, created_at__date=today
        ).count()

        high_risk_patients = patients_qs.filter(
            surgery__risk_level=Surgery.RiskLevels.HIGH
        ).count()

        # No dedicated appointments model yet – surface 0 for now.
        appointments_today = 0

        alerts = []
        tasks = []
        for patient in patients_qs:
            care = getattr(patient, 'care_summary', None)
            insights = (care.ai_insights or {}) if care else {}
            for msg in insights.get('risk_assessments', [])[:3]:
                alerts.append(
                    {
                        'patient_id': patient.id,
                        'patient_name': patient.full_name,
                        'label': 'AI Alert',
                        'message': msg,
                        'severity': 'high',
                    }
                )
            for msg in insights.get('recommended_actions', [])[:3]:
                tasks.append(
                    {
                        'patient_id': patient.id,
                        'patient_name': patient.full_name,
                        'task': msg,
                        'status': 'pending',
                    }
                )

        data = HospitalDashboardSerializer(
            {
                'total_patients': total_patients,
                'surgeries_today': surgeries_today,
                'high_risk_patients': high_risk_patients,
                'appointments_today': appointments_today,
                'alerts': alerts,
                'tasks': tasks,
            }
        ).data
        return Response(data)
