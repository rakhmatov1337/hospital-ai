from django.contrib import admin

from .models import (
    ActivityPlan,
    ActivityPlanItem,
    DietPlan,
    DietPlanFoodItem,
    DietPlanMeal,
    Medication,
    Surgery,
)


class DietPlanFoodItemInline(admin.TabularInline):
    model = DietPlanFoodItem
    extra = 1


class DietPlanMealInline(admin.TabularInline):
    model = DietPlanMeal
    extra = 1


@admin.register(DietPlan)
class DietPlanAdmin(admin.ModelAdmin):
    list_display = ('summary', 'diet_type', 'goal_calories')
    search_fields = ('summary', 'diet_type')
    inlines = [DietPlanFoodItemInline, DietPlanMealInline]


class ActivityPlanItemInline(admin.TabularInline):
    model = ActivityPlanItem
    extra = 1


@admin.register(ActivityPlan)
class ActivityPlanAdmin(admin.ModelAdmin):
    list_display = ('id',)
    inlines = [ActivityPlanItemInline]


@admin.register(Surgery)
class SurgeryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'risk_level', 'hospital')
    list_filter = ('risk_level', 'hospital')
    search_fields = ('name', 'type', 'hospital__name')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'patient', 'surgery', 'start_date', 'end_date')
    list_filter = ('surgery', 'start_date')
