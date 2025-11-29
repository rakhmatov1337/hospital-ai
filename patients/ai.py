import json
import logging
import os
from typing import Any, Dict, Optional

from django.conf import settings
from openai import OpenAI

from patients.models import Patient, PatientCarePlan

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a medical assistant that outputs detailed, empathetic care guidance for post-surgical patients.
Return structured data that can populate UI cards for care plan, diet, activities, and AI insights.
Keep each bullet concise (<= 20 words) and clinically sound.
Respond ONLY with JSON in this shape:
{
  "care_plan": {"pre_op": [""...], "post_op": ["..."]},
  "diet_plan": {
    "summary": {"diet_type": "", "goal_calories": "", "notes": ""},
    "allowed_foods": [""...],
    "forbidden_foods": [""...],
    "meal_plan": [""...]
  },
  "activities": {"allowed": [""...], "restricted": [""...]},
  "ai_insights": {
    "priority_level_assessments": [""...],
    "predictive_analytics": [""...],
    "recommended_actions": [""...]
  }
}
"""

SYSTEM_PROMPT_INSIGHTS = """
Siz tibbiy AI yordamchisisiz, bemor va operatsiya ma'lumotlarini tahlil qilib, klinik tushunchalar va parvarish ko'rsatmalarini taqdim etasiz.
Bemorning to'liq ma'lumotlari (yoshi, jinsi, holati, tayinlangan shifokor, palata) va operatsiya tafsilotlari (nomi, tavsifi, turi, ustuvorlik darajasi, dori-darmonlar) asosida tuzilgan AI tushunchalari va parvarish rejasini yarating.

FAQAT JSON formatida javob bering:
{
  "care_plan": {
    "recovery_instructions": [
      "Dastlabki 24 soat davomida har soatda hayotiy belgilarni kuzatib boring.",
      "Tavsiya etilgan dori-darmonlar bilan og'riqni boshqaring.",
      "Pnevmoniyani oldini olish uchun chuqur nafas olish mashqlarini rag'batlantiring.",
      "Operatsiyadan keyin imkoniyat darajasida harakatlanishga yordam bering.",
      "Yara baholash uchun keyingi uchrashuvni rejalashtiring."
    ],
    "after_discharged_instructions": [
      "Ko'rsatilganidek dori-darmonlarni qabul qilishni davom eting.",
      "Kesilgan joyni toza va quruq saqlang.",
      "7-10 kundan keyin shifokoringiz bilan uchrashuvni rejalashtiring.",
      "Tavsiya etilgan muddat davomida jiddiy faoliyatlardan qoching.",
      "Har qanday infektsiya yoki asorat belgilarini darhol xabar qiling."
    ]
  },
  "priority_level_assessments": [
    "Kesilgan joyda infektsiya belgilarini kuzatib boring.",
    "Quyi oyoq-qo'llarda qon laxtalari ehtimolini baholang."
  ],
  "predictive_analytics": [
    "Boshqa shunga o'xshash holatlarga asoslanib tiklanish vaqtini bashorat qiling.",
    "Bemor profiliga asoslanib asoratlar ehtimolini baholang."
  ],
  "recommended_actions": [
    "1-10 shkalada og'riq darajasini tez-tez baholang.",
    "Tiklanishga yordam berish uchun suv iste'molini rag'batlantiring.",
    "Yara parvarishi va asorat belgilari haqida ma'lumot bering."
  ],
  "tasks": [
    "Ertalabki dori-darmonni qabul qiling",
    "Nonushta - ovqatlanish rejasiga rioya qiling",
    "Tushdan keyingi dori-darmonni qabul qiling",
    "Jiddiy faoliyatlardan qoching",
    "Kechki dori-darmon eslatmasi"
  ]
}

Ko'rsatmalar:
- care_plan.recovery_instructions: Kasalxonada tiklanish davrida bemor parvarishi uchun 4-6 ta ko'rsatma ro'yxati.
- care_plan.after_discharged_instructions: Chiqarilgandan keyin bemor parvarishi uchun 4-6 ta ko'rsatma ro'yxati.
- priority_level_assessments: Operatsiyaning ustuvorlik darajasi va bemor profiliga asoslanib 2-4 ta maxsus monitoring ogohlantirishlari. "Yuqori ustuvorlik" yoki "O'rtacha ustuvorlik" terminologiyasidan foydalaning.
- predictive_analytics: Tiklanish vaqti, asoratlar yoki natijalar haqida 2-3 ta bashoratli tushunchalar.
- recommended_actions: Bemor parvarishi uchun 3-5 ta amaliy klinik tavsiyalar.
- tasks: Bemor uchun 5 ta kunlik vazifa ro'yxati (o'zbek tilida).
- Har bir element qisqa (15-30 so'z) va klinik jihatdan muhim bo'lishi kerak.
- Tushunchalar operatsiyaning ustuvorlik darajasi (past, o'rtacha, yuqori) va bemor xususiyatlariga asoslanishi kerak.
"""


def _get_client() -> Optional[OpenAI]:
    api_key = settings.OPENAI_API_KEY or os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning('OPENAI_API_KEY is not configured; skipping care plan generation.')
        return None
    return OpenAI(api_key=api_key)


def _build_patient_payload(patient: Patient) -> Dict[str, Any]:
    surgery = patient.surgery
    surgery_type_name = None
    if surgery and surgery.type:
        surgery_type_name = surgery.type.name if hasattr(surgery.type, 'name') else str(surgery.type)
    
    return {
        'patient': {
            'name': patient.full_name,
            'age': patient.age,
            'gender': patient.gender,
            'status': patient.status,
            'assigned_doctor': patient.assigned_doctor,
            'admitted_at': patient.admitted_at.isoformat() if patient.admitted_at else None,
        },
        'surgery': {
            'name': surgery.name if surgery else None,
            'description': surgery.description if surgery else None,
            'type': surgery_type_name,
            'type_description': surgery.type.description if surgery and surgery.type and hasattr(surgery.type, 'description') else None,
            'priority_level': surgery.priority_level if surgery else None,
        },
        'medications': [
            {'name': med.name, 'dosage': med.dosage, 'frequency': med.frequency, 'start_date': str(med.start_date), 'end_date': str(med.end_date)}
            for med in (surgery.medications.all() if surgery else [])
        ],
    }


def generate_patient_care_plan(patient: Patient) -> Optional[Dict[str, Any]]:
    client = _get_client()
    if not client:
        return None

    payload = _build_patient_payload(patient)

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {
            'role': 'user',
            'content': f'Create a structured care plan JSON for this patient:\n{json.dumps(payload)}',
        },
    ]

    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={'type': 'json_object'},
        )
    except Exception as exc:  # pragma: no cover - network
        logger.exception('Failed to generate care plan for patient %s: %s', patient.pk, exc)
        return None

    try:
        content = response.choices[0].message.content or '{}'
        return json.loads(content)
    except Exception as exc:  # pragma: no cover - parsing guard
        logger.error('Unable to parse care plan response for patient %s: %s', patient.pk, exc)
        return None


def generate_and_store_care_plan(patient: Patient) -> None:
    data = generate_patient_care_plan(patient)
    if not data:
        return
    PatientCarePlan.objects.update_or_create(
        patient=patient,
        defaults={
            'care_plan': data.get('care_plan', {}),
            'diet_plan': data.get('diet_plan', {}),
            'activities': data.get('activities', {}),
            'ai_insights': data.get('ai_insights', {}),
        },
    )


def generate_ai_insights(patient: Patient) -> Optional[Dict[str, Any]]:
    """
    Generate AI insights (priority level assessments, predictive analytics, recommended actions)
    based on patient and surgery information.
    """
    client = _get_client()
    if not client:
        logger.warning('OpenAI client not available; skipping AI insights generation.')
        return None
    
    if not patient.surgery:
        logger.warning('Patient has no surgery assigned; cannot generate AI insights.')
        return None
    
    payload = _build_patient_payload(patient)
    
    user_prompt = f"""Ushbu bemor uchun parvarish rejasi va AI tushunchalarini yarating:

Bemor ma'lumotlari:
- Ism: {payload['patient']['name']}
- Yosh: {payload['patient']['age']}
- Jins: {payload['patient']['gender']}
- Holat: {payload['patient']['status']}
- Tayinlangan shifokor: {payload['patient']['assigned_doctor']}
- Qabul qilingan sana: {payload['patient']['admitted_at']}

Operatsiya ma'lumotlari:
- Nomi: {payload['surgery']['name']}
- Tavsifi: {payload['surgery']['description']}
- Turi: {payload['surgery']['type']}
- Tur tavsifi: {payload['surgery'].get('type_description', 'N/A')}
- Ustuvorlik darajasi: {payload['surgery']['priority_level']}

Dori-darmonlar:
{json.dumps(payload['medications'], indent=2) if payload['medications'] else 'Hali tayinlanmagan.'}

Ushbu ma'lumotlarga asoslanib yarating:
1. Parvarish rejasi recovery_instructions (kasalxonada tiklanish uchun) va after_discharged_instructions (chiqarilgandan keyingi parvarish uchun) bilan
2. Ustuvorlik darajasi baholashlari
3. Bashoratli tahlillar
4. Tavsiya etilgan harakatlar
5. Kunlik vazifalar ro'yxati (tasks)"""

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT_INSIGHTS},
        {'role': 'user', 'content': user_prompt},
    ]
    
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={'type': 'json_object'},
            max_tokens=800,
            temperature=0.7,
        )
    except Exception as exc:
        logger.exception('Failed to generate AI insights for patient %s: %s', patient.pk, exc)
        return None
    
    try:
        content = response.choices[0].message.content or '{}'
        insights = json.loads(content)
        # Ensure all required fields exist
        return {
            'care_plan': insights.get('care_plan', {
                'recovery_instructions': [],
                'after_discharged_instructions': []
            }),
            'priority_level_assessments': insights.get('priority_level_assessments', []),
            'predictive_analytics': insights.get('predictive_analytics', []),
            'recommended_actions': insights.get('recommended_actions', []),
            'tasks': insights.get('tasks', []),
        }
    except Exception as exc:
        logger.error('Unable to parse AI insights response for patient %s: %s', patient.pk, exc)
        return None


def generate_and_store_ai_insights(patient: Patient) -> None:
    """Generate and store AI insights, care plan, and tasks for a patient."""
    from patients.models import Task
    
    insights_data = generate_ai_insights(patient)
    if not insights_data:
        return
    
    # Extract care_plan and ai_insights separately
    care_plan = insights_data.get('care_plan', {})
    ai_insights = {
        'priority_level_assessments': insights_data.get('priority_level_assessments', []),
        'predictive_analytics': insights_data.get('predictive_analytics', []),
        'recommended_actions': insights_data.get('recommended_actions', []),
    }
    
    PatientCarePlan.objects.update_or_create(
        patient=patient,
        defaults={
            'care_plan': care_plan,
            'ai_insights': ai_insights,
        },
    )
    
    # Create tasks from AI-generated task list
    tasks = insights_data.get('tasks', [])
    for task_label in tasks:
        Task.objects.get_or_create(
            patient=patient,
            label=task_label,
            defaults={'completed': False}
        )

