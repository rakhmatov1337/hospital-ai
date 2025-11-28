from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from patients.models import Patient
from patients.permissions import IsPatientUser


class PatientHomeView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def get(self, request):
        user = request.user
        try:
            patient: Patient = user.patient_profile
        except Patient.DoesNotExist:  # type: ignore[attr-defined]
            return Response({'detail': 'No patient profile found.'}, status=404)

        today = timezone.localdate()

        medications_today = patient.medications.filter(
            start_date__lte=today, end_date__gte=today
        )
        medications_count = medications_today.count()

        surgery = patient.surgery
        care = getattr(patient, 'care_summary', None)

        greeting = f'Hi, {patient.full_name.split()[0]}' if patient.full_name else 'Hi'

        # Simple status inference based on risk and status
        status_message = 'On track'
        if surgery and surgery.risk_level == surgery.RiskLevels.HIGH:
            status_message = 'Caution advised'
        if patient.status in [patient.StatusChoices.CRITICAL, patient.StatusChoices.IN_SURGERY]:
            status_message = 'Critical – follow instructions closely'

        alerts = []
        tasks = []
        if care:
            alerts = care.ai_insights.get('risk_assessments', [])
            tasks = care.ai_insights.get('recommended_actions', [])

        data = {
            'greeting': greeting,
            'subtitle': "Here's your recovery today",
            'banner': {
                'type': 'warning',
                'message': 'With your current symptoms, caution is advised today.',
            },
            'cards': {
                'medications': {
                    'label': 'Medications',
                    'count': medications_count,
                    'status': f'{medications_count} today',
                },
                'diet_plan': {
                    'label': 'Diet Plan',
                    'status': 'On track',
                },
                'activities': {
                    'label': 'Activities',
                    'status': 'View safe',
                },
                'appointments': {
                    'label': 'Appointments',
                    'next': None,
                },
            },
            'today_tasks': [
                {
                    'label': 'Take morning medication',
                    'completed': False,
                },
                {
                    'label': 'Breakfast – follow meal plan',
                    'completed': False,
                },
                {
                    'label': 'Take afternoon medication',
                    'completed': False,
                },
                {
                    'label': 'Avoid strenuous activities',
                    'completed': False,
                },
                {
                    'label': 'Evening medication reminder',
                    'completed': False,
                },
            ],
            'ai_alerts': alerts,
        }

        return Response(data)
