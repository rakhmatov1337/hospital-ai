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

        # Get tasks from Task model
        from patients.models import Task
        tasks = Task.objects.filter(patient=patient).order_by('created_at')
        
        tasks_data = [
            {
                'id': task.id,
                'label': task.label,
                'completed': task.completed,
            }
            for task in tasks
        ]

        return Response({'tasks': tasks_data})


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
        if not patient.surgery:
            return Response({'detail': 'No surgery assigned to patient.'}, status=404)
        
        meds_qs = (
            Medication.objects.filter(
                surgery=patient.surgery,
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
Ruxsat etilgan faoliyatlar: {', '.join(allowed) if allowed else "Ko'rsatilmagan"}
Cheklangan faoliyatlar: {', '.join(restricted) if restricted else "Ko'rsatilmagan"}
Faoliyat rejasi eslatmalari: {activity_plan.notes or "Yo'q"}
"""

        system_prompt = """Siz operatsiyadan keyingi bemorlarga faoliyatlar tiklanish uchun xavfsiz ekanligini tushunishda yordam beradigan tibbiy yordamchisisiz.
Bemorning to'liq ma'lumotlariga asoslanib, so'ralgan faoliyat xavfsiz ekanligi haqida qisqa (50-100 so'z), aniq va amaliy javob bering.
Xavflar va tavsiyalar haqida aniq bo'ling. Og'irlik o'lchovlarida faqat kilogramm (kg) ishlating, funt (lbs) ishlatmang.
Har doim bemorni tibbiy maslahat uchun shifokoriga murojaat qilishni eslatib o'ting."""

        # Get care plan information
        care = getattr(patient, 'care_summary', None)
        care_plan_info = ''
        if care and care.care_plan:
            recovery = care.care_plan.get('recovery_instructions', [])
            if recovery:
                care_plan_info = f"\nParvarish rejasi: {', '.join(recovery[:2])}\n"

        # Get AI insights
        ai_insights_info = ''
        if care and care.ai_insights:
            insights = care.ai_insights
            priority_assessments = insights.get('priority_level_assessments', [])
            if priority_assessments:
                ai_insights_info = f"\nUstuvorlik baholashlari: {', '.join(priority_assessments[:1])}\n"

        # Build medications list
        medications_list = []
        if payload.get('medications'):
            for m in payload['medications']:
                medications_list.append(f"- {m['name']} ({m['dosage']})")
        medications_text = '\n'.join(medications_list) if medications_list else 'Hali tayinlanmagan.'

        days_since_admission = (timezone.now().date() - patient.admitted_at.date()).days if patient.admitted_at else 'Noma\'lum'

        user_prompt = f"""Bemorning to'liq ma'lumotlari:
- Ism: {payload['patient'].get('name') or 'Noma\'lum'}
- Yosh: {payload['patient'].get('age') or 'Noma\'lum'}
- Jins: {payload['patient'].get('gender') or 'Noma\'lum'}
- Holat: {payload['patient'].get('status') or 'Noma\'lum'}
- Tayinlangan shifokor: {payload['patient'].get('assigned_doctor') or 'Noma\'lum'}
- Qabul qilingan sana: {payload['patient'].get('admitted_at') or 'Noma\'lum'}
- Qabul qilingandan beri kunlar: {days_since_admission}

Operatsiya ma'lumotlari:
- Operatsiya nomi: {payload['surgery'].get('name') or 'Noma\'lum'}
- Operatsiya tavsifi: {payload['surgery'].get('description') or 'Noma\'lum'}
- Operatsiya turi: {payload['surgery'].get('type') or 'Noma\'lum'}
- Ustuvorlik darajasi: {payload['surgery'].get('priority_level') or 'Noma\'lum'}

Dori-darmonlar:
{medications_text}

Faoliyat rejasi:
{activity_context}
{care_plan_info}
{ai_insights_info}

Bemor savoli: {question}

Iltimos, bu faoliyat bemorning tiklanishi uchun xavfsiz ekanligi haqida qisqa va aniq javob bering."""

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            answer = response.choices[0].message.content or 'Javob yaratib bo\'lmadi.'
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
            diet_summary = f" Ovqatlanish rejasi: {surgery.diet_plan.summary} ({surgery.diet_plan.diet_type})."
        if surgery and surgery.activity_plan:
            activity_summary = f" Faoliyat eslatmalari: {surgery.activity_plan.notes or 'Yo\'q'}."

        system_prompt = (
            "Siz operatsiyadan keyingi bemorlarga yordam beradigan AI tiklanish yordamchisisiz. "
            "Berilgan to'liq bemor ma'lumotlaridan foydalanib, savollarga qisqa (50-100 so'z), aniq va amaliy javob bering. "
            "Javobingiz sodda, tushunarli va bemor uchun foydali bo'lishi kerak. "
            "Og'irlik o'lchovlarida faqat kilogramm (kg) ishlating, funt (lbs) ishlatmang. "
            "Hech qachon tibbiy maslahatni bekor qilmang; har doim bemorni shifokorining ko'rsatmalariga rioya qilishni eslatib o'ting."
        )

        # Get care plan information
        care = getattr(patient, 'care_summary', None)
        care_plan_info = ''
        if care and care.care_plan:
            recovery = care.care_plan.get('recovery_instructions', [])
            after_discharge = care.care_plan.get('after_discharged_instructions', [])
            if recovery or after_discharge:
                care_plan_info = f"\nParvarish rejasi:\n"
                if recovery:
                    care_plan_info += f"Tiklanish ko'rsatmalari: {', '.join(recovery[:3])}\n"
                if after_discharge:
                    care_plan_info += f"Chiqarilgandan keyingi ko'rsatmalar: {', '.join(after_discharge[:3])}\n"

        # Get AI insights
        ai_insights_info = ''
        if care and care.ai_insights:
            insights = care.ai_insights
            priority_assessments = insights.get('priority_level_assessments', [])
            if priority_assessments:
                ai_insights_info = f"\nUstuvorlik baholashlari: {', '.join(priority_assessments[:2])}\n"

        # Get tasks
        from patients.models import Task
        tasks = Task.objects.filter(patient=patient, completed=False)
        tasks_info = ''
        if tasks.exists():
            tasks_info = f"\nKunlik vazifalar: {', '.join([t.label for t in tasks[:3]])}\n"

        # Build medications list
        medications_list = []
        if payload.get('medications'):
            for m in payload['medications']:
                medications_list.append(f"- {m['name']} ({m['dosage']}) - {m['frequency']}")
        medications_text = '\n'.join(medications_list) if medications_list else 'Hali tayinlanmagan.'

        user_prompt = (
            f"Bemorning to'liq ma'lumotlari:\n"
            f"- Ism: {payload['patient'].get('name') or 'Noma\'lum'}\n"
            f"- Yosh: {payload['patient'].get('age') or 'Noma\'lum'}\n"
            f"- Jins: {payload['patient'].get('gender') or 'Noma\'lum'}\n"
            f"- Holat: {payload['patient'].get('status') or 'Noma\'lum'}\n"
            f"- Tayinlangan shifokor: {payload['patient'].get('assigned_doctor') or 'Noma\'lum'}\n"
            f"- Qabul qilingan sana: {payload['patient'].get('admitted_at') or 'Noma\'lum'}\n"
            f"\nOperatsiya ma'lumotlari:\n"
            f"- Operatsiya nomi: {payload['surgery'].get('name') or 'Noma\'lum'}\n"
            f"- Operatsiya tavsifi: {payload['surgery'].get('description') or 'Noma\'lum'}\n"
            f"- Operatsiya turi: {payload['surgery'].get('type') or 'Noma\'lum'}\n"
            f"- Ustuvorlik darajasi: {payload['surgery'].get('priority_level') or 'Noma\'lum'}\n"
            f"\nDori-darmonlar:\n{medications_text}\n"
            f"{diet_summary}{activity_summary}"
            f"{care_plan_info}"
            f"{ai_insights_info}"
            f"{tasks_info}"
            f"\nBemor savoli: {question}\n\n"
            f"Yuqoridagi barcha ma'lumotlarga asoslanib, qisqa va aniq javob bering."
        )

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            answer = response.choices[0].message.content or 'Javob yaratib bo\'lmadi.'

            # Quick suggestions in Uzbek
            suggestions = [
                'Dori-darmonlar jadvalimni tushuntirib bering',
                'Qanday ovqatlardan qochishim kerak?',
                'Bugun jismoniy mashq qila olamanmi?',
                'Bosh og\'rig\'im bor, nima qilishim kerak?',
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

    def patch(self, request, task_id):
        patient = getattr(request.user, 'patient_profile', None)
        if not patient:
            return Response({'detail': 'No patient profile found.'}, status=404)

        try:
            from patients.models import Task
            task = Task.objects.get(id=task_id, patient=patient)
        except Task.DoesNotExist:
            return Response({'detail': 'Task not found.'}, status=404)
        
        completed = request.data.get('completed')
        if completed is None:
            return Response({'detail': 'completed field is required.'}, status=400)
        
        task.completed = bool(completed)
        task.save(update_fields=['completed', 'updated_at'])
        
        return Response({
            'id': task.id,
            'label': task.label,
            'completed': task.completed,
        })
