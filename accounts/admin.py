from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from hospitals.models import Hospital

from .models import User


class HospitalInline(admin.StackedInline):
    model = Hospital
    can_delete = False
    fk_name = 'user'
    extra = 0
    verbose_name_plural = 'Hospital profile'


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Role information', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    inlines = (HospitalInline,)

    def get_inline_instances(self, request, obj=None):
        """
        Only show the hospital inline when creating/editing hospital users.
        """
        if not obj:
            return [inline(self.model, self.admin_site) for inline in self.inlines]
        if obj.role == User.Roles.HOSPITAL:
            return [inline(self.model, self.admin_site) for inline in self.inlines]
        return []
