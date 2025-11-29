from rest_framework import serializers

from accounts.models import User
from hospitals.models import Hospital
# AI generation removed - diet plan comes from surgery
from patients.models import MedicalRecord, Patient, PatientCarePlan, RecordText
from surgeries.models import Medication, Surgery
from surgeries.serializers import (
    ActivityPlanDisplaySerializer,
    DietPlanDisplaySerializer,
    MedicationSerializer,
)


class SurgerySerializer(serializers.ModelSerializer):
    diet_plan = DietPlanDisplaySerializer(read_only=True)
    activity_plan = ActivityPlanDisplaySerializer(read_only=True)

    class Meta:
        model = Surgery
        fields = ['id', 'name', 'description', 'type', 'priority_level', 'diet_plan', 'activity_plan']


class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        ref_name = 'PatientMedication'
        fields = ['id', 'name', 'dosage', 'frequency', 'start_date', 'end_date']
        read_only_fields = fields


class PatientMedicationCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    dosage = serializers.CharField()
    frequency = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.CharField()
    due_time = serializers.CharField()


class RecordTextSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordText
        fields = ['id', 'text', 'date']
        read_only_fields = fields


class MedicalRecordSerializer(serializers.ModelSerializer):
    record_text = RecordTextSerializer(read_only=True)

    class Meta:
        model = MedicalRecord
        fields = ['id', 'record_title', 'record_text']
        read_only_fields = fields


class PatientListSerializer(serializers.ModelSerializer):
    surgery_id = serializers.IntegerField(source='surgery.id', read_only=True, allow_null=True)
    surgery_name = serializers.CharField(source='surgery.name', read_only=True)
    surgery_priority_level = serializers.CharField(
        source='surgery.priority_level', read_only=True
    )

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'phone',
            'assigned_doctor',
            'surgery_id',
            'surgery_name',
            'surgery_priority_level',
            'status',
        ]
        read_only_fields = fields


class PatientCarePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientCarePlan
        fields = ['care_plan', 'ai_insights', 'updated_at']
        read_only_fields = fields


class PatientDetailSerializer(serializers.ModelSerializer):
    hospital = serializers.SlugRelatedField(
        read_only=True,
        slug_field='name',
    )
    surgery = SurgerySerializer(read_only=True)
    medications = serializers.SerializerMethodField()
    medical_records = MedicalRecordSerializer(many=True, read_only=True)
    care_bundle = PatientCarePlanSerializer(source='care_summary', read_only=True)
    
    def get_medications(self, obj):
        if obj.surgery:
            return MedicationSerializer(obj.surgery.medications.all(), many=True).data
        return []

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'age',
            'gender',
            'phone',
            'assigned_doctor',
            'admitted_at',
            'status',
            'hospital',
            'surgery',
            'medications',
            'medical_records',
            'care_bundle',
        ]
        read_only_fields = fields


class PatientWriteSerializer(serializers.ModelSerializer):
    surgery_id = serializers.PrimaryKeyRelatedField(
        source='surgery', queryset=Surgery.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Patient
        fields = [
            'id',
            'full_name',
            'age',
            'gender',
            'phone',
            'assigned_doctor',
            'admitted_at',
            'status',
            'surgery_id',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        hospital = self.context.get('hospital')
        if hospital is None or not isinstance(hospital, Hospital):
            raise serializers.ValidationError('Hospital context is required.')
        return attrs

    def create(self, validated_data):
        # Always bind patient to the hospital user who is creating it
        hospital = self.context.get('hospital')
        if hospital is not None and isinstance(hospital, Hospital):
            validated_data['hospital'] = hospital

        phone = validated_data['phone']
        if User.objects.filter(username=phone).exists():
            raise serializers.ValidationError(
                {'phone': 'A user with this phone already exists.'}
            )
        user = User.objects.create_user(
            username=phone,
            password=phone,
            role=User.Roles.PATIENT,
        )
        validated_data['user'] = user
        patient = super().create(validated_data)
        
        # Generate and store AI insights
        from patients.ai import generate_and_store_ai_insights
        generate_and_store_ai_insights(patient)
        
        return patient

    def update(self, instance, validated_data):
        # Ensure hospital cannot be changed via this serializer; keep current one
        hospital = self.context.get('hospital')
        if hospital is not None and isinstance(hospital, Hospital):
            validated_data['hospital'] = hospital

        phone = validated_data.get('phone')
        if phone and phone != instance.phone:
            qs = User.objects.filter(username=phone)
            if instance.user_id:
                qs = qs.exclude(pk=instance.user_id)
            if qs.exists():
                raise serializers.ValidationError(
                    {'phone': 'A user with this phone already exists.'}
                )
            user = instance.user or User.objects.create_user(
                username=phone,
                password=phone,
                role=User.Roles.PATIENT,
            )
            user.username = phone
            user.set_password(phone)
            user.save(update_fields=['username', 'password'])
            validated_data['user'] = user
        patient = super().update(instance, validated_data)
        return patient


class ActivitySafetyCheckSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=500,
        help_text='Question about activity safety (e.g., "Can I go jogging?")',
    )


class AIChatSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=1000,
        help_text='Free-form question for the AI recovery assistant.',
    )


class TaskSerializer(serializers.Serializer):
    label = serializers.CharField()
    completed = serializers.BooleanField()


class UpdateTasksSerializer(serializers.Serializer):
    today_tasks = TaskSerializer(many=True)

