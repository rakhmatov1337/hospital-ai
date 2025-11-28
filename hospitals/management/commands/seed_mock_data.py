from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from hospitals.models import Hospital
from patients.ai import generate_and_store_care_plan
from patients.models import MedicalRecord, Patient, PatientCarePlan, RecordText
from surgeries.models import (
    ActivityPlan,
    ActivityPlanItem,
    DietPlan,
    DietPlanFoodItem,
    DietPlanMeal,
    Medication,
    Surgery,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed database with a demo hospital, patients, surgeries, and related data.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Seeding mock data...'))

        hospital_user, created = User.objects.get_or_create(
            username='hospital',
            defaults={
                'email': 'hospital@example.com',
                'role': User.Roles.HOSPITAL,
                'is_staff': True,
                'is_superuser': False,
            },
        )
        if created:
            hospital_user.set_password('Sunocun20')
            hospital_user.save()
            self.stdout.write(self.style.SUCCESS('Created hospital user "hospital".'))
        else:
            self.stdout.write(self.style.WARNING('Hospital user "hospital" already exists.'))

        hospital, _ = Hospital.objects.get_or_create(
            user=hospital_user,
            defaults={
                'name': 'Cofound Orthopedic Center',
                'description': 'Demo orthopedic surgery center for mock data.',
                'administrator': 'Dr. Admin User',
            },
        )

        # Diet & activity plans shared by surgeries
        diet_plan = DietPlan.objects.create(
            summary='Post-op knee replacement diet',
            diet_type='Low-Sodium, High-Protein',
            goal_calories=2000,
            protein_target='100g/day',
            notes='Focus on lean proteins and low sodium to reduce swelling.',
        )
        for name in [
            'Lean chicken and turkey',
            'Fish (salmon, cod)',
            'Fresh vegetables',
            'Whole grains',
            'Low-fat dairy',
        ]:
            DietPlanFoodItem.objects.create(
                plan=diet_plan,
                category=DietPlanFoodItem.Categories.ALLOWED,
                name=name,
            )
        for name in ['Processed meats', 'Fried foods', 'Sugary desserts', 'Alcohol']:
            DietPlanFoodItem.objects.create(
                plan=diet_plan,
                category=DietPlanFoodItem.Categories.FORBIDDEN,
                name=name,
            )
        DietPlanMeal.objects.create(
            plan=diet_plan,
            meal_type='Breakfast',
            description='Oatmeal with berries, scrambled eggs, herbal tea',
            time='08:00',
        )
        DietPlanMeal.objects.create(
            plan=diet_plan,
            meal_type='Dinner',
            description='Baked salmon, quinoa, steamed broccoli, water',
            time='19:00',
        )

        activity_plan = ActivityPlan.objects.create(
            notes='Progress activities as tolerated; avoid impact early.',
        )
        for name in [
            'Gentle walking (10–15 minutes)',
            'Seated exercises',
            'Upper body stretches',
            'Physical therapy exercises',
        ]:
            ActivityPlanItem.objects.create(
                plan=activity_plan,
                category=ActivityPlanItem.Categories.ALLOWED,
                name=name,
            )
        for name in [
            'Running or jogging',
            'Jumping or hopping',
            'Heavy lifting (>10 lbs)',
            'Contact sports',
        ]:
            ActivityPlanItem.objects.create(
                plan=activity_plan,
                category=ActivityPlanItem.Categories.RESTRICTED,
                name=name,
            )

        # Surgeries
        knee_surgery, _ = Surgery.objects.get_or_create(
            name='Total Knee Replacement',
            hospital=hospital,
            defaults={
                'description': 'Right knee arthroplasty for osteoarthritis.',
                'type': 'Orthopedic',
                'risk_level': Surgery.RiskLevels.HIGH,
                'diet_plan': diet_plan,
                'activity_plan': activity_plan,
            },
        )

        app_surgery, _ = Surgery.objects.get_or_create(
            name='Appendectomy',
            hospital=hospital,
            defaults={
                'description': 'Removal of inflamed appendix.',
                'type': 'General Surgery',
                'risk_level': Surgery.RiskLevels.MEDIUM,
                'diet_plan': diet_plan,
                'activity_plan': activity_plan,
            },
        )

        # Patients
        base_admit = timezone.now() - timedelta(days=3)
        demo_patients = [
            {
                'full_name': 'John Martinez',
                'age': 58,
                'gender': Patient.GenderChoices.MALE,
                'phone': '5551234567',
                'assigned_doctor': 'Dr. Sarah Johnson',
                'admitted_at': base_admit,
                'ward': 'Ward A - Room 204',
                'status': Patient.StatusChoices.IN_RECOVERY,
                'surgery': knee_surgery,
            },
            {
                'full_name': 'Emma Williams',
                'age': 46,
                'gender': Patient.GenderChoices.FEMALE,
                'phone': '5552345678',
                'assigned_doctor': 'Dr. Michael Chen',
                'admitted_at': base_admit - timedelta(days=1),
                'ward': 'Ward B - Room 105',
                'status': Patient.StatusChoices.STABLE,
                'surgery': app_surgery,
            },
        ]

        for pdata in demo_patients:
            user, _ = User.objects.get_or_create(
                username=pdata['phone'],
                defaults={
                    'role': User.Roles.PATIENT,
                },
            )
            user.set_password(pdata['phone'])
            user.save()

            patient, created = Patient.objects.get_or_create(
                phone=pdata['phone'],
                defaults={
                    'user': user,
                    'hospital': hospital,
                    **{k: v for k, v in pdata.items() if k not in ['phone']},
                },
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created patient {patient.full_name}.'))

            # Simple medical record
            record_text = RecordText.objects.create(
                patient=patient,
                text='Post-op day 2: pain controlled, mobilizing with assistance.',
                date=date.today(),
            )
            MedicalRecord.objects.create(
                patient=patient,
                record_title='Post-op Progress',
                record_text=record_text,
            )

            # Medication
            Medication.objects.get_or_create(
                surgery=patient.surgery,
                patient=patient,
                name='Cefazolin',
                dosage='1 g IV',
                frequency='Every 8 hours',
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() + timedelta(days=2),
            )

            # AI care plan
            if not hasattr(patient, 'care_summary'):
                generate_and_store_care_plan(patient)

        self.stdout.write(self.style.SUCCESS('Mock data seeding complete.'))


