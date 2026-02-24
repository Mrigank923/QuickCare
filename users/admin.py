from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserAddress, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['contact', 'name', 'email', 'roles', 'is_active', 'date_joined']
    list_filter = ['roles', 'is_active', 'gender']
    search_fields = ['contact', 'name', 'email']
    ordering = ['-date_joined']
    fieldsets = (
        (None, {'fields': ('contact', 'password')}),
        ('Personal Info', {'fields': ('name', 'email', 'age', 'gender', 'avatar')}),
        ('Roles & Status', {'fields': ('roles', 'is_active', 'is_staff', 'is_partial_onboarding', 'is_complete_onboarding')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('contact', 'name', 'roles', 'password1', 'password2'),
        }),
    )


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'address_type', 'town', 'state', 'pincode', 'is_current']
    list_filter = ['address_type', 'is_current']
    search_fields = ['user__contact', 'user__name', 'town', 'pincode']
