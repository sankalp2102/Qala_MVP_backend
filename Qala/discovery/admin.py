# discovery/admin.py
from django.contrib import admin
from .models import BuyerProfile, StudioRecommendation, CustomInquiry, StudioInquiry


@admin.register(BuyerProfile)
class BuyerProfileAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'display_name', 'user', 'journey_stage',
        'batch_size', 'matching_complete', 'created_at',
    ]
    list_filter    = ['journey_stage', 'batch_size', 'matching_complete', 'craft_interest']
    search_fields  = ['first_name', 'last_name', 'id', 'user__email']
    readonly_fields = ['id', 'session_token', 'created_at', 'updated_at']
    ordering       = ['-created_at']
    raw_id_fields  = ['user']


@admin.register(StudioRecommendation)
class StudioRecommendationAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'buyer_profile', 'seller_profile',
        'rank_position', 'ranking', 'is_bonus_visual', 'created_at',
    ]
    list_filter    = ['ranking', 'is_bonus_visual', 'core_capability_fit']
    search_fields  = ['buyer_profile__first_name', 'seller_profile__profile_name']
    readonly_fields = ['id', 'created_at']
    ordering       = ['buyer_profile', 'rank_position']
    raw_id_fields  = ['buyer_profile', 'seller_profile']
    
@admin.register(CustomInquiry)
class CustomInquiryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'created_at', 'buyer_profile']
    list_filter   = ['created_at']
    search_fields = ['name', 'email', 'message']
    readonly_fields = ['id', 'created_at', 'buyer_profile']
    ordering = ['-created_at']
@admin.register(StudioInquiry)
class StudioInquiryAdmin(admin.ModelAdmin):
    list_display   = ['name', 'email', 'seller_profile', 'created_at', 'buyer_profile']
    list_filter    = ['created_at', 'seller_profile']
    search_fields  = ['name', 'email', 'seller_profile__studio_details__studio_name']
    readonly_fields = ['id', 'created_at', 'buyer_profile', 'answers']
    ordering       = ['-created_at']
    raw_id_fields  = ['seller_profile', 'buyer_profile']
