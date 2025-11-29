from typing import Any, Dict

from rest_framework import serializers

from hospitals.models import Hospital
from patients.models import Patient
from surgeries.models import (
    ActivityPlan,
    ActivityPlanItem,
    DietPlan,
    DietPlanFoodItem,
    DietPlanMeal,
    Medication,
    Surgery,
    SurgeryType,
)


class SimpleNameSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class MealPlanSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    meal_type = serializers.CharField(max_length=50)
    description = serializers.CharField()
    time = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class DietPlanPayloadSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=255)
    # Simple string label for diet type (e.g. "Low-Sodium, High-Protein")
    diet_type = serializers.CharField(max_length=100)
    goal_calories = serializers.IntegerField(min_value=0)
    protein_target = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    allowed_foods = SimpleNameSerializer(many=True, required=False)
    forbidden_foods = SimpleNameSerializer(many=True, required=False)
    meal_plan = MealPlanSerializer(many=True, required=False)


class ActivityPlanPayloadSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    allowed = SimpleNameSerializer(many=True, required=False)
    restricted = SimpleNameSerializer(many=True, required=False)


class DietPlanMealModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietPlanMeal
        fields = ['id', 'meal_type', 'description', 'time']


class DietPlanDisplaySerializer(serializers.ModelSerializer):
    allowed_foods = serializers.SerializerMethodField()
    forbidden_foods = serializers.SerializerMethodField()
    meal_plan = DietPlanMealModelSerializer(many=True, read_only=True)
    # For convenience in hospital lists, expose diet_type_name aliasing diet_type.
    diet_type_name = serializers.SerializerMethodField()

    class Meta:
        model = DietPlan
        fields = [
            'id',
            'summary',
            'diet_type',
            'diet_type_name',
            'goal_calories',
            'protein_target',
            'notes',
            'allowed_foods',
            'forbidden_foods',
            'meal_plan',
        ]

    def _serialize_foods(self, obj, category: str):
        items = obj.food_items.filter(category=category)
        return SimpleNameSerializer(items, many=True).data

    def get_allowed_foods(self, obj):
        return self._serialize_foods(obj, DietPlanFoodItem.Categories.ALLOWED)

    def get_forbidden_foods(self, obj):
        return self._serialize_foods(obj, DietPlanFoodItem.Categories.FORBIDDEN)

    def get_diet_type_name(self, obj):
        """
        Alias for diet_type so the client can use a consistent name field.
        """
        return obj.diet_type


class ActivityPlanDisplaySerializer(serializers.ModelSerializer):
    allowed = serializers.SerializerMethodField()
    restricted = serializers.SerializerMethodField()

    class Meta:
        model = ActivityPlan
        fields = ['id', 'notes', 'allowed', 'restricted']

    def _serialize(self, obj, category: str):
        items = obj.activities.filter(category=category)
        return SimpleNameSerializer(items, many=True).data

    def get_allowed(self, obj):
        return self._serialize(obj, ActivityPlanItem.Categories.ALLOWED)

    def get_restricted(self, obj):
        return self._serialize(obj, ActivityPlanItem.Categories.RESTRICTED)


class SurgeryTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurgeryType
        fields = ['id', 'name', 'description']


class SurgeryListSerializer(serializers.ModelSerializer):
    type = SurgeryTypeSerializer(read_only=True)
    
    class Meta:
        model = Surgery
        fields = ['id', 'name', 'type', 'priority_level', 'description']


class SurgeryDetailSerializer(serializers.ModelSerializer):
    type = SurgeryTypeSerializer(read_only=True)
    diet_plan = DietPlanDisplaySerializer(read_only=True)
    activity_plan = ActivityPlanDisplaySerializer(read_only=True)

    class Meta:
        model = Surgery
        fields = [
            'id',
            'name',
            'description',
            'type',
            'priority_level',
            'diet_plan',
            'activity_plan',
        ]


class SurgeryWriteSerializer(serializers.ModelSerializer):
    type_id = serializers.PrimaryKeyRelatedField(
        source='type', queryset=SurgeryType.objects.all(), allow_null=True, required=False
    )
    # Existing nested create/update payloads
    diet_plan = DietPlanPayloadSerializer(required=False)
    activity_plan = ActivityPlanPayloadSerializer(required=False)
    # New: link to existing plans by id
    diet_plan_id = serializers.PrimaryKeyRelatedField(
        source='diet_plan', queryset=DietPlan.objects.all(), allow_null=True, required=False
    )
    activity_plan_id = serializers.PrimaryKeyRelatedField(
        source='activity_plan', queryset=ActivityPlan.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Surgery
        fields = [
            'id',
            'name',
            'description',
            'type_id',
            'priority_level',
            'diet_plan',
            'activity_plan',
            'diet_plan_id',
            'activity_plan_id',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        diet_data = validated_data.pop('diet_plan', None)
        activity_data = validated_data.pop('activity_plan', None)
        hospital: Hospital = self.context['hospital']
        surgery = Surgery.objects.create(hospital=hospital, **validated_data)
        # If nested dicts are provided, upsert; if existing instances are provided via *_id, just assign.
        if isinstance(diet_data, dict):
            surgery.diet_plan = self._upsert_diet_plan(surgery.diet_plan, diet_data)
        elif isinstance(diet_data, DietPlan):
            surgery.diet_plan = diet_data
        if isinstance(activity_data, dict):
            surgery.activity_plan = self._upsert_activity_plan(surgery.activity_plan, activity_data)
        elif isinstance(activity_data, ActivityPlan):
            surgery.activity_plan = activity_data
        surgery.save()
        return surgery

    def update(self, instance, validated_data):
        diet_data = validated_data.pop('diet_plan', None)
        activity_data = validated_data.pop('activity_plan', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if isinstance(diet_data, dict):
            instance.diet_plan = self._upsert_diet_plan(instance.diet_plan, diet_data)
        elif isinstance(diet_data, DietPlan):
            instance.diet_plan = diet_data
        if isinstance(activity_data, dict):
            instance.activity_plan = self._upsert_activity_plan(instance.activity_plan, activity_data)
        elif isinstance(activity_data, ActivityPlan):
            instance.activity_plan = activity_data
        instance.save()
        return instance

    def to_representation(self, instance):
        return SurgeryDetailSerializer(instance, context=self.context).data

    def _upsert_diet_plan(self, plan: DietPlan | None, data: Dict[str, Any]) -> DietPlan:
        hospital: Hospital = self.context.get('hospital')
        plan = plan or DietPlan()
        plan.hospital = hospital
        plan.summary = data['summary']
        # Store the human-readable diet type string
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

    def _upsert_activity_plan(self, plan: ActivityPlan | None, data: Dict[str, Any]) -> ActivityPlan:
        hospital: Hospital = self.context.get('hospital')
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


class MedicationSerializer(serializers.ModelSerializer):
    surgery_id = serializers.PrimaryKeyRelatedField(
        source='surgery', queryset=Surgery.objects.all()
    )

    class Meta:
        model = Medication
        ref_name = 'SurgeryMedication'
        fields = [
            'id',
            'surgery_id',
            'name',
            'dosage',
            'frequency',
            'start_date',
            'end_date',
        ]
        read_only_fields = ['id']

