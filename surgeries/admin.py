from django.contrib import admin

from .models import ActivityPlan, DietPlan, Medication, Surgery


@admin.register(DietPlan)
class DietPlanAdmin(admin.ModelAdmin):
    list_display = ('summary', 'diet_type', 'goal_calories')
    search_fields = ('summary', 'diet_type')


@admin.register(ActivityPlan)
class ActivityPlanAdmin(admin.ModelAdmin):
    list_display = ('id',)


@admin.register(Surgery)
class SurgeryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'risk_level')
    list_filter = ('risk_level',)
    search_fields = ('name', 'type')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'patient', 'surgery', 'start_date', 'end_date')
    list_filter = ('surgery', 'start_date')
