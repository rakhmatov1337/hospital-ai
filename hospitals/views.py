from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from typing import Any, Dict

from rest_framework import viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import HospitalTokenObtainPairSerializer
from hospitals.permissions import IsHospitalUser
from hospitals.serializers import (
    HospitalAIChatSerializer,
    HospitalDashboardSerializer,
    HospitalSerializer,
)
from patients.ai import _build_patient_payload, _get_client
from patients.models import Patient
from patients.serializers import (
    PatientDetailSerializer,
    PatientListSerializer,
    PatientWriteSerializer,
)
from surgeries.models import (
    ActivityPlan,
    ActivityPlanItem,
    DietPlan,
    DietPlanFoodItem,
    DietPlanMeal,
    Medication,
    Surgery,
)
from surgeries.serializers import (
    ActivityPlanDisplaySerializer,
    ActivityPlanPayloadSerializer,
    DietPlanDisplaySerializer,
    DietPlanPayloadSerializer,
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
        
        queryset = (
            Patient.objects.filter(hospital=hospital)
            .select_related('surgery', 'hospital', 'care_summary')
            .prefetch_related(
                'medical_records__record_text',
            )
        )
        
        # Search functionality
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(phone__icontains=search)
            )
        
        # Filter by Surgery
        surgery_id = self.request.query_params.get('surgery_id', None)
        if surgery_id:
            queryset = queryset.filter(surgery_id=surgery_id)
        
        # Filter by Priority Level (from surgery)
        priority_level = self.request.query_params.get('priority_level', None)
        if priority_level:
            queryset = queryset.filter(surgery__priority_level=priority_level)
        
        # Filter by Doctor
        doctor = self.request.query_params.get('doctor', None)
        if doctor:
            queryset = queryset.filter(assigned_doctor__icontains=doctor)
        
        return queryset.order_by('-id')

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
        ).select_related('surgery').order_by('-id')

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
            .order_by('-id')
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


class HospitalDietPlanViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsHospitalUser)

    def get_queryset(self):
        hospital = self._get_hospital()
        if hospital is None:
            return DietPlan.objects.none()
        return (
            DietPlan.objects.filter(hospital=hospital)
            .prefetch_related('food_items', 'meals')
            .order_by('-id')
        )

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return DietPlanPayloadSerializer
        return DietPlanDisplaySerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        hospital = self._get_hospital()
        if hospital is not None:
            context['hospital'] = hospital
        return context

    def perform_create(self, serializer):
        hospital = self._get_hospital()
        serializer.save(hospital=hospital)

    def _upsert_diet_plan(self, plan: DietPlan | None, data: Dict[str, Any]) -> DietPlan:
        from hospitals.models import Hospital
        hospital: Hospital = self._get_hospital()
        plan = plan or DietPlan()
        plan.hospital = hospital
        plan.summary = data['summary']
        plan.diet_type = data['diet_type']
        plan.goal_calories = data['goal_calories']
        plan.protein_target = data.get('protein_target', '')
        plan.notes = data.get('notes', '')
        plan.save()

        plan.food_items.all().delete()
        for item in data.get('allowed_foods', []):
            DietPlanFoodItem.objects.create(
                plan=plan,
                category=DietPlanFoodItem.Categories.ALLOWED,
                name=item['name'],
                description=item.get('description') or '',
            )
        for item in data.get('forbidden_foods', []):
            DietPlanFoodItem.objects.create(
                plan=plan,
                category=DietPlanFoodItem.Categories.FORBIDDEN,
                name=item['name'],
                description=item.get('description') or '',
            )

        plan.meals.all().delete()
        for meal in data.get('meal_plan', []):
            DietPlanMeal.objects.create(
                plan=plan,
                meal_type=meal['meal_type'],
                description=meal['description'],
                time=meal.get('time', ''),
            )
        return plan

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = self._upsert_diet_plan(None, serializer.validated_data)
        return Response(DietPlanDisplaySerializer(plan).data, status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = self._upsert_diet_plan(instance, serializer.validated_data)
        return Response(DietPlanDisplaySerializer(plan).data)

    def _get_hospital(self):
        if getattr(self, 'swagger_fake_view', False):
            return None
        hospital = getattr(self.request.user, 'hospital_profile', None)
        if hospital is None:
            raise ValidationError('No hospital profile is linked to this account.')
        return hospital


class HospitalActivityPlanViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsHospitalUser)

    def get_queryset(self):
        hospital = self._get_hospital()
        if hospital is None:
            return ActivityPlan.objects.none()
        return (
            ActivityPlan.objects.filter(hospital=hospital)
            .prefetch_related('activities')
            .order_by('-id')
        )

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ActivityPlanPayloadSerializer
        return ActivityPlanDisplaySerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        hospital = self._get_hospital()
        if hospital is not None:
            context['hospital'] = hospital
        return context

    def perform_create(self, serializer):
        hospital = self._get_hospital()
        serializer.save(hospital=hospital)

    def _upsert_activity_plan(self, plan: ActivityPlan | None, data: Dict[str, Any]) -> ActivityPlan:
        from hospitals.models import Hospital
        hospital: Hospital = self._get_hospital()
        plan = plan or ActivityPlan()
        plan.hospital = hospital
        plan.notes = data.get('notes', '')
        plan.save()

        plan.activities.all().delete()
        for item in data.get('allowed', []):
            ActivityPlanItem.objects.create(
                plan=plan,
                category=ActivityPlanItem.Categories.ALLOWED,
                name=item['name'],
                description=item.get('description') or '',
            )
        for item in data.get('restricted', []):
            ActivityPlanItem.objects.create(
                plan=plan,
                category=ActivityPlanItem.Categories.RESTRICTED,
                name=item['name'],
                description=item.get('description') or '',
            )
        return plan

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = self._upsert_activity_plan(None, serializer.validated_data)
        return Response(ActivityPlanDisplaySerializer(plan).data, status=201)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = self._upsert_activity_plan(instance, serializer.validated_data)
        return Response(ActivityPlanDisplaySerializer(plan).data)

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

        from django.utils import timezone

        patients_qs = Patient.objects.filter(hospital=hospital).select_related(
            'surgery', 'care_summary'
        )
        total_patients = patients_qs.count()

        recovery_patients = patients_qs.filter(
            status=Patient.StatusChoices.IN_RECOVERY
        ).count()

        discharged_patients = patients_qs.filter(
            status=Patient.StatusChoices.DISCHARGED
        ).count()

        high_priority_patients = patients_qs.filter(
            surgery__priority_level=Surgery.PriorityLevels.HIGH
        ).count()

        # Recent patients (last 10, ordered by most recently admitted)
        recent_patients_list = patients_qs.order_by('-admitted_at')[:10]
        recent_patients = [
            {
                'id': p.id,
                'full_name': p.full_name,
                'status': p.status,
                'surgery_name': p.surgery.name if p.surgery else None,
                'priority_level': p.surgery.priority_level if p.surgery else None,
                'admitted_at': p.admitted_at,
            }
            for p in recent_patients_list
        ]

        data = HospitalDashboardSerializer(
            {
                'total_patients': total_patients,
                'recovery_patients': recovery_patients,
                'discharged_patients': discharged_patients,
                'high_priority_patients': high_priority_patients,
                'recent_patients': recent_patients,
            }
        ).data
        return Response(data)


class HospitalAIChatView(APIView):
    """
    AI medical assistant for hospital users.
    Can answer questions about recovery, priority, and patient care, optionally scoped to a specific patient.
    """

    permission_classes = (IsAuthenticated, IsHospitalUser)

    def post(self, request):
        serializer = HospitalAIChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data['question']
        patient_id = serializer.validated_data.get('patient_id')

        hospital = getattr(request.user, 'hospital_profile', None)
        if hospital is None:
            raise NotFound('No hospital profile is linked to this account.')

        client = _get_client()
        if not client:
            return Response(
                {'detail': 'AI service is not available. Please try again later.'},
                status=503,
            )

        patient = None
        payload = {}
        
        # If patient_id is provided, use it
        if patient_id is not None:
            try:
                patient = Patient.objects.select_related('surgery').get(
                    id=patient_id, hospital=hospital
                )
            except Patient.DoesNotExist:
                raise NotFound('Patient not found for this hospital.')
        else:
            # Try to find patient by name, phone, or surgery in the question
            import re
            from django.db.models import Q
            
            # Extract potential names (capitalized words that might be names)
            words = re.findall(r'\b[A-Z][a-z]+\b', question)
            # Extract phone numbers
            phone_numbers = re.findall(r'\b\d{9,}\b', question)
            
            if phone_numbers:
                # Search by phone number first (most specific)
                potential_patients = Patient.objects.filter(
                    hospital=hospital,
                    phone__icontains=phone_numbers[0]
                ).select_related('surgery')
                if potential_patients.exists():
                    patient = potential_patients.first()
            
            if not patient and words:
                # Search for patients whose name contains any of these words
                for word in words:
                    potential_patients = Patient.objects.filter(
                        hospital=hospital,
                        full_name__icontains=word
                    ).select_related('surgery')
                    
                    if potential_patients.count() == 1:
                        patient = potential_patients.first()
                        break
                    elif potential_patients.count() > 1:
                        # Check if surgery name is mentioned in question
                        surgery_names = []
                        for p in potential_patients:
                            if p.surgery and p.surgery.name.lower() in question.lower():
                                surgery_names.append(p)
                        
                        if len(surgery_names) == 1:
                            patient = surgery_names[0]
                            break
                        
                        # Multiple patients with same name - ask for clarification
                        patients_list = []
                        for p in potential_patients[:5]:  # Limit to 5 to avoid too long response
                            surgery_info = f" ({p.surgery.name})" if p.surgery else ""
                            patients_list.append(f"- {p.full_name} (Telefon: {p.phone}{surgery_info})")
                        
                        clarification = (
                            f"Bir nechta bemor topildi '{word}' ismi bilan. "
                            f"Iltimos, quyidagilardan birini tanlang:\n" + 
                            "\n".join(patients_list) +
                            "\n\nYoki telefon raqam yoki operatsiya nomini ko'rsating."
                        )
                        
                        return Response({
                            'answer': clarification,
                            'suggestions': [],
                            'patient_id': None,
                            'patient_name': None,
                            'requires_clarification': True,
                            'potential_patients': [
                                {
                                    'id': p.id,
                                    'name': p.full_name,
                                    'phone': p.phone,
                                    'surgery': p.surgery.name if p.surgery else None,
                                }
                                for p in potential_patients[:5]
                            ],
                        })

        if patient:
            payload = _build_patient_payload(patient)

        # Load chat history (last 10 messages for context)
        from hospitals.models import HospitalChatMessage
        chat_history = HospitalChatMessage.objects.filter(
            hospital=hospital,
            user=request.user
        ).order_by('-created_at')[:10]
        
        # Build conversation history for AI context
        conversation_history = []
        for msg in reversed(chat_history):  # Reverse to get chronological order
            conversation_history.append({
                'role': 'user',
                'content': msg.question
            })
            conversation_history.append({
                'role': 'assistant',
                'content': msg.answer
            })

        # Build hospital-level summary
        today = timezone.localdate()
        total_patients = Patient.objects.filter(hospital=hospital).count()
        surgeries_today = Surgery.objects.filter(
            hospital=hospital, created_at__date=today
        ).count()

        system_prompt = (
            "Siz kasalxona xodimlariga bemor parvarishi, "
            "tiklanish monitoringi, ustuvorlik baholash va tibbiy ma'lumotlarni sodda tushuntirishda yordam beradigan AI tibbiy yordamchisisiz. "
            "Agar bemor ma'lumotlari berilgan bo'lsa, bemorning holati, vazifalar bajarilishi, tiklanish progressi va tavsiyalar haqida batafsil javob bering. "
            "Javoblarni qisqa tuting (<= 250 so'z) va aniq tashxis qo'yishdan qoching. "
            "Bemor haqida savol bo'lsa, bemorning barcha ma'lumotlarini, vazifalar bajarilishini va tiklanish progressini tahlil qiling va amaliy tavsiyalar bering. "
            "Oldingi suhbatlar kontekstini eslab qoling va ularga murojaat qiling. "
            "MUHIM: Javobingizni faqat oddiy matn sifatida yozing. Hech qanday markdown formatidan foydalanmang: **, -, *, _, #, va boshqa formatlash belgilari ishlatmang. "
            "Faqat oddiy matn, vergul va nuqta ishlating. Ma'lumotlarni oddiy qatorlar sifatida yozing, formatlash belgilari bo'lmasin. "
            "Har doim yakuniy qarorlar litsenziyalangan klinisyenlarga tegishli ekanligini eslatib o'ting."
        )

        hospital_context = (
            f"Kasalxona: {hospital.name}. Jami bemorlar: {total_patients}. "
            f"Bugungi operatsiyalar: {surgeries_today}."
        )

        if patient and payload:
            # Get task completion information
            from patients.models import Task
            tasks = Task.objects.filter(patient=patient)
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(completed=True).count()
            pending_tasks = total_tasks - completed_tasks
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Get care plan information
            care = getattr(patient, 'care_summary', None)
            care_plan_info = ''
            if care and care.care_plan:
                recovery = care.care_plan.get('recovery_instructions', [])
                after_discharge = care.care_plan.get('after_discharged_instructions', [])
                if recovery:
                    care_plan_info = f"\nTiklanish ko'rsatmalari: {', '.join(recovery[:3])}"
                if after_discharge:
                    care_plan_info += f"\nChiqarilgandan keyingi ko'rsatmalar: {', '.join(after_discharge[:2])}"
            
            # Get AI insights
            ai_insights_info = ''
            if care and care.ai_insights:
                insights = care.ai_insights
                priority_assessments = insights.get('priority_level_assessments', [])
                predictive_analytics = insights.get('predictive_analytics', [])
                recommended_actions = insights.get('recommended_actions', [])
                if priority_assessments:
                    ai_insights_info = f"\nUstuvorlik baholashlari: {', '.join(priority_assessments[:2])}"
                if predictive_analytics:
                    ai_insights_info += f"\nBashoratli tahlillar: {', '.join(predictive_analytics[:2])}"
                if recommended_actions:
                    ai_insights_info += f"\nTavsiya etilgan harakatlar: {', '.join(recommended_actions[:3])}"
            
            # Build medications list
            medications_list = []
            if payload.get('medications'):
                for m in payload['medications']:
                    medications_list.append(f"- {m['name']} ({m['dosage']}) - {m['frequency']}")
            medications_text = '\n'.join(medications_list) if medications_list else 'Hali tayinlanmagan.'
            
            patient_context = (
                f"Bemorning to'liq ma'lumotlari:\n"
                f"- Ism: {payload['patient'].get('name') or 'Noma\'lum'}\n"
                f"- Yosh: {payload['patient'].get('age') or 'Noma\'lum'}\n"
                f"- Jins: {payload['patient'].get('gender') or 'Noma\'lum'}\n"
                f"- Holat: {payload['patient'].get('status') or 'Noma\'lum'}\n"
                f"- Tayinlangan shifokor: {payload['patient'].get('assigned_doctor') or 'Noma\'lum'}\n"
                f"- Palata: {payload['patient'].get('ward') or 'Noma\'lum'}\n"
                f"- Qabul qilingan sana: {payload['patient'].get('admitted_at') or 'Noma\'lum'}\n"
                f"\nOperatsiya ma'lumotlari:\n"
                f"- Operatsiya nomi: {payload['surgery'].get('name') or 'Noma\'lum'}\n"
                f"- Operatsiya tavsifi: {payload['surgery'].get('description') or 'Noma\'lum'}\n"
                f"- Operatsiya turi: {payload['surgery'].get('type') or 'Noma\'lum'}\n"
                f"- Ustuvorlik darajasi: {payload['surgery'].get('priority_level') or 'Noma\'lum'}\n"
                f"\nDori-darmonlar:\n{medications_text}\n"
                f"\nVazifalar holati:\n"
                f"- Jami vazifalar: {total_tasks}\n"
                f"- Bajarilgan: {completed_tasks}\n"
                f"- Kutilayotgan: {pending_tasks}\n"
                f"- Bajarilish foizi: {completion_rate:.1f}%\n"
                f"{care_plan_info}\n"
                f"{ai_insights_info}"
            )
        else:
            patient_context = "Maxsus bemor tanlanmagan; umumiy klinik darajada javob bering."

        user_prompt = (
            f"{hospital_context}\n"
            f"{patient_context}\n\n"
            f"Klinisyen savoli: {question}\n\n"
            "Kasalxona dashboard UI'ida ko'rinishi mumkin bo'lgan tuzilgan, klinik jihatdan foydali javob bering. "
            "Javobingizni faqat oddiy matn sifatida yozing, hech qanday formatlash belgilari (**, -, *, va boshqalar) ishlatmang."
        )

        try:
            # Build messages with conversation history
            messages = [
                {'role': 'system', 'content': system_prompt},
            ]
            # Add conversation history
            messages.extend(conversation_history)
            # Add current question
            messages.append({'role': 'user', 'content': user_prompt})
            
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                max_tokens=800,
                temperature=0.5,
            )
            answer = response.choices[0].message.content or 'Javob yaratib bo\'lmadi.'
            
            # Strip markdown formatting and newlines from answer
            import re
            # Remove bold markers **text** -> text
            answer = re.sub(r'\*\*(.*?)\*\*', r'\1', answer)
            # Remove italic markers *text* -> text
            answer = re.sub(r'\*(.*?)\*', r'\1', answer)
            # Remove underscore markers _text_ -> text
            answer = re.sub(r'_(.*?)_', r'\1', answer)
            # Remove heading markers # text -> text
            answer = re.sub(r'^#+\s*', '', answer, flags=re.MULTILINE)
            # Remove bullet points - -> (replace with space or remove)
            answer = re.sub(r'^-\s*', '', answer, flags=re.MULTILINE)
            # Replace all newlines with spaces
            answer = re.sub(r'\n+', ' ', answer)
            # Replace multiple spaces with single space
            answer = re.sub(r'\s+', ' ', answer)
            answer = answer.strip()
            
            # Save chat message to database
            HospitalChatMessage.objects.create(
                hospital=hospital,
                user=request.user,
                question=question,
                answer=answer,
                patient=patient,
            )
            
            # Generate suggestions if patient is found
            suggestions = []
            if patient:
                suggestions = [
                    f"{patient.full_name}ning tiklanish progressi qanday?",
                    f"{patient.full_name}ning vazifalarini bajarilishini tahlil qiling",
                    f"{patient.full_name} uchun tavsiyalar bering",
                    f"{patient.full_name}ning dori-darmonlarini ko'rib chiqing",
                ]
            else:
                suggestions = [
                    "Bemorlar ro'yxatini ko'rsating",
                    "Bugungi operatsiyalar haqida ma'lumot bering",
                    "Yuqori ustuvorlikdagi bemorlar kimlar?",
                    "Tiklanish progressi qanday?",
                ]
            
            return Response({
                'answer': answer,
                'suggestions': suggestions,
                'patient_id': patient.id if patient else None,
                'patient_name': patient.full_name if patient else None,
            })
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception('Failed to generate hospital AI chat response: %s', exc)
            return Response(
                {'detail': 'Failed to generate AI response. Please try again later.'},
                status=500,
            )
