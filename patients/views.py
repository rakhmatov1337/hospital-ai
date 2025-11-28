from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import PatientTokenObtainPairSerializer
from patients.ai import _build_patient_payload, _get_client
from patients.models import Patient
from patients.permissions import IsPatientUser
from patients.serializers import (
    AIChatSerializer,
    ActivitySafetyCheckSerializer,
    PatientDetailSerializer,
    PatientMedicationCardSerializer,
    UpdateTasksSerializer,
)
from surgeries.models import Medication
from surgeries.serializers import ActivityPlanDisplaySerializer, DietPlanDisplaySerializer


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
            'today_tasks': self._get_today_tasks(care),
            'ai_alerts': alerts,
        }

        return Response(data)

    def _get_today_tasks(self, care):
        """Get today's tasks from care plan or return defaults."""
        default_tasks = [
            {'label': 'Take morning medication', 'completed': False},
            {'label': 'Breakfast – follow meal plan', 'completed': False},
            {'label': 'Take afternoon medication', 'completed': False},
            {'label': 'Avoid strenuous activities', 'completed': False},
            {'label': 'Evening medication reminder', 'completed': False},
        ]
        
        if care and care.today_tasks:
            # Merge saved tasks with defaults (preserve order and labels)
            saved_dict = {task.get('label'): task for task in care.today_tasks}
            result = []
            for default_task in default_tasks:
                label = default_task['label']
                if label in saved_dict:
                    result.append(saved_dict[label])
                else:
                    result.append(default_task)
            return result
        return default_tasks


class PatientTokenObtainPairView(TokenObtainPairView):
    serializer_class = PatientTokenObtainPairSerializer
    permission_classes = (AllowAny,)


class PatientMeView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def get(self, request):
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)
        data = PatientDetailSerializer(patient).data
        return Response(data)


class PatientMedicationsView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def get(self, request):
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        today = timezone.localdate()
        meds_qs = (
            Medication.objects.filter(
                patient=patient,
                start_date__lte=today,
                end_date__gte=today,
            )
            .order_by('start_date', 'id')
        )

        # Simple time slots to mimic the UI (8 AM, 2 PM, 8 PM)
        slots = ['8:00 AM', '2:00 PM', '8:00 PM']
        cards = []
        for i, med in enumerate(meds_qs):
            status = 'taken' if i == 0 else 'upcoming'
            due_time = slots[i % len(slots)]
            cards.append(
                {
                    'id': med.id,
                    'name': med.name,
                    'dosage': med.dosage,
                    'frequency': med.frequency,
                    'start_date': med.start_date,
                    'end_date': med.end_date,
                    'status': status,
                    'due_time': due_time,
                }
            )

        serializer = PatientMedicationCardSerializer(cards, many=True)

        def _flag(label_time: str) -> bool:
            return any(c['due_time'] == label_time for c in cards)

        return Response(
            {
                'medications': serializer.data,
                'timeline': [
                    {'label': '8 AM', 'has_medications': _flag('8:00 AM')},
                    {'label': '12 PM', 'has_medications': False},
                    {'label': '2 PM', 'has_medications': _flag('2:00 PM')},
                    {'label': '6 PM', 'has_medications': _flag('8:00 PM')},
                ],
            }
        )


class PatientDietPlanView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def get(self, request):
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        surgery = patient.surgery
        if not surgery or not surgery.diet_plan:
            return Response({'detail': 'No diet plan available.'}, status=404)

        serializer = DietPlanDisplaySerializer(surgery.diet_plan)
        return Response(serializer.data)


class PatientActivitiesView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def get(self, request):
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        surgery = patient.surgery
        if not surgery or not surgery.activity_plan:
            return Response({'detail': 'No activity plan available.'}, status=404)

        activity_plan = surgery.activity_plan
        serializer = ActivityPlanDisplaySerializer(activity_plan)
        
        # Add general guidelines based on the activity plan notes
        guidelines = []
        if activity_plan.notes:
            # Split notes by newlines or common separators
            note_lines = [line.strip() for line in activity_plan.notes.split('\n') if line.strip()]
            guidelines = note_lines if note_lines else []
        
        # Default guidelines if none provided
        if not guidelines:
            guidelines = [
                'Start slowly and gradually increase activity',
                'Stop if you experience pain or discomfort',
                'Rest when needed and don\'t push yourself',
                'Consult your doctor before starting new activities',
            ]
        
        data = serializer.data
        data['general_guidelines'] = guidelines
        return Response(data)


class ActivitySafetyCheckView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def post(self, request):
        serializer = ActivitySafetyCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']

        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        client = _get_client()
        if not client:
            return Response(
                {'detail': 'AI service is not available. Please contact your healthcare provider.'},
                status=503,
            )

        # Build context from patient data
        payload = _build_patient_payload(patient)
        
        # Get activity plan context
        activity_context = ''
        if patient.surgery and patient.surgery.activity_plan:
            activity_plan = patient.surgery.activity_plan
            allowed = [item.name for item in activity_plan.activities.filter(category='allowed')]
            restricted = [item.name for item in activity_plan.activities.filter(category='restricted')]
            activity_context = f"""
Allowed activities: {', '.join(allowed) if allowed else 'None specified'}
Restricted activities: {', '.join(restricted) if restricted else 'None specified'}
Activity plan notes: {activity_plan.notes or 'None'}
"""

        system_prompt = """You are a medical assistant helping post-surgical patients understand if activities are safe for their recovery.
Based on the patient's surgery, current status, and activity plan, provide a clear, concise answer about whether the asked activity is safe.
Be specific about risks and recommendations. Keep your response under 150 words.
Always remind the patient to consult their doctor for medical advice."""

        user_prompt = f"""Patient Information:
- Surgery: {payload['surgery'].get('name', 'Unknown')} ({payload['surgery'].get('type', 'Unknown')})
- Risk Level: {payload['surgery'].get('risk_level', 'Unknown')}
- Current Status: {payload['patient'].get('status', 'Unknown')}
- Days since admission: {(timezone.now().date() - patient.admitted_at.date()).days if patient.admitted_at else 'Unknown'}

Activity Plan:
{activity_context}

Patient Question: {question}

Please provide a clear, helpful answer about whether this activity is safe for this patient's recovery."""

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                max_tokens=300,
                temperature=0.7,
            )
            answer = response.choices[0].message.content or 'Unable to generate response.'
            return Response({'answer': answer})
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception('Failed to generate activity safety check: %s', exc)
            return Response(
                {'detail': 'Failed to generate AI response. Please try again later.'},
                status=500,
            )


class PatientAIChatView(APIView):
    """
    General AI chat endpoint for patients.
    The AI sees the patient's surgery, medications, care plan and activity/diet context.
    """

    permission_classes = (IsAuthenticated, IsPatientUser)

    def post(self, request):
        serializer = AIChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']

        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        client = _get_client()
        if not client:
            return Response(
                {'detail': 'AI service is not available. Please contact your healthcare provider.'},
                status=503,
            )

        payload = _build_patient_payload(patient)

        # Optional extra context from surgery plans
        surgery = patient.surgery
        diet_summary = ''
        activity_summary = ''
        if surgery and surgery.diet_plan:
            diet_summary = f" Diet plan: {surgery.diet_plan.summary} ({surgery.diet_plan.diet_type})."
        if surgery and surgery.activity_plan:
            activity_summary = f" Activity notes: {surgery.activity_plan.notes or 'None'}."

        system_prompt = (
            "You are an AI recovery assistant helping a post-surgical patient. "
            "Use the provided clinical context (surgery, risk level, medications, status, diet and activity plans) "
            "to answer questions about medications, diet, activities and symptoms. "
            "Be empathetic, concise (<= 180 words), and practical. "
            "Never override medical advice; always remind the patient to follow their doctor's instructions."
        )

        user_prompt = (
            "Patient Context:\n"
            f"- Name: {payload['patient'].get('name') or 'Unknown'}\n"
            f"- Age: {payload['patient'].get('age') or 'Unknown'}\n"
            f"- Gender: {payload['patient'].get('gender') or 'Unknown'}\n"
            f"- Status: {payload['patient'].get('status') or 'Unknown'}\n"
            f"- Surgery: {payload['surgery'].get('name') or 'Unknown'} "
            f"({payload['surgery'].get('type') or 'Unknown'})\n"
            f"- Risk level: {payload['surgery'].get('risk_level') or 'Unknown'}\n"
            f"- Medications: {', '.join([m['name'] for m in payload.get('medications', [])]) or 'None listed.'}\n"
            f"{diet_summary}{activity_summary}\n\n"
            f"Patient question: {question}\n\n"
            "Answer as if chatting in a recovery assistant app UI."
        )

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                max_tokens=350,
                temperature=0.7,
            )
            answer = response.choices[0].message.content or 'Unable to generate response.'

            # Simple quick suggestions – frontend can override if needed
            suggestions = [
                'Explain my medication schedule',
                'What foods should I avoid?',
                'Can I exercise today?',
                'I have a headache, what should I do?',
            ]

            return Response({'answer': answer, 'suggestions': suggestions})
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception('Failed to generate AI chat response: %s', exc)
            return Response(
                {'detail': 'Failed to generate AI response. Please try again later.'},
                status=500,
            )


class PatientTasksUpdateView(APIView):
    permission_classes = (IsAuthenticated, IsPatientUser)

    def patch(self, request):
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        serializer = UpdateTasksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get or create care plan
        from patients.models import PatientCarePlan
        care, _ = PatientCarePlan.objects.get_or_create(patient=patient)
        
        # Update today_tasks
        care.today_tasks = serializer.validated_data['today_tasks']
        care.save(update_fields=['today_tasks', 'updated_at'])
        
        return Response({'today_tasks': care.today_tasks})
