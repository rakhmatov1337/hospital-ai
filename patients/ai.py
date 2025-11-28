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
    "risk_assessments": [""...],
    "predictive_analytics": [""...],
    "recommended_actions": [""...]
  }
}
"""


def _get_client() -> Optional[OpenAI]:
    api_key = settings.OPENAI_API_KEY or os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning('OPENAI_API_KEY is not configured; skipping care plan generation.')
        return None
    return OpenAI(api_key=api_key)


def _build_patient_payload(patient: Patient) -> Dict[str, Any]:
    return {
        'patient': {
            'name': patient.full_name,
            'age': patient.age,
            'gender': patient.gender,
            'status': patient.status,
            'assigned_doctor': patient.assigned_doctor,
            'ward': patient.ward,
            'admitted_at': patient.admitted_at.isoformat() if patient.admitted_at else None,
        },
        'surgery': {
            'name': patient.surgery.name if patient.surgery else None,
            'description': patient.surgery.description if patient.surgery else None,
            'type': patient.surgery.type if patient.surgery else None,
            'risk_level': patient.surgery.risk_level if patient.surgery else None,
        },
        'medications': [
            {'name': med.name, 'dosage': med.dosage, 'frequency': med.frequency}
            for med in patient.medications.all()
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

