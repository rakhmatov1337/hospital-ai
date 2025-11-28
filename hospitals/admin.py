from django.contrib import admin

from .models import Hospital


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('name', 'administrator', 'created_at')
    search_fields = ('name', 'administrator')
