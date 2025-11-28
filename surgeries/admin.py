from django.contrib import admin

from .models import (
    ActivityPlan,
    ActivityPlanItem,
    DietPlan,
    DietPlanFoodItem,
    DietPlanMeal,
    Medication,
    Surgery,
    SurgeryType,
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


@admin.register(SurgeryType)
class SurgeryTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


@admin.register(Surgery)
class SurgeryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'priority_level', 'hospital')
    list_filter = ('priority_level', 'hospital', 'type')
    search_fields = ('name', 'type__name', 'hospital__name')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'surgery', 'start_date', 'end_date')
    list_filter = ('surgery', 'start_date')
