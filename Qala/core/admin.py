# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AdminProfile, SellerAccount, SellerProfile, CustomerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ['email', 'role', 'is_active', 'date_joined']
    list_filter    = ['role', 'is_active']
    search_fields  = ['email']
    ordering       = ['-date_joined']
    fieldsets = (
        (None,           {'fields': ('email', 'password')}),
        ('Role & Status',{'fields': ('role', 'is_active', 'is_staff', 'supertokens_id')}),
        ('Permissions',  {'fields': ('is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'password1', 'password2', 'role'),
        }),
    )


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'user', 'permissions_level', 'created_at']
    search_fields = ['full_name', 'user__email']


@admin.register(SellerAccount)
class SellerAccountAdmin(admin.ModelAdmin):
    list_display  = ['business_name', 'user', 'is_verified', 'created_by', 'created_at']
    list_filter   = ['is_verified']
    search_fields = ['business_name', 'user__email']


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display  = ['profile_name', 'seller_account', 'is_active', 'is_default']
    list_filter   = ['is_active', 'is_default']
    search_fields = ['profile_name', 'seller_account__business_name']


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'user', 'city', 'country', 'created_at']
    search_fields = ['full_name', 'user__email']