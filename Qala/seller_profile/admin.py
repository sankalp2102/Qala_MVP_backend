# seller_profile/admin.py
# BUG 13 FIX: register all 16 models so you can inspect data during testing
from django.contrib import admin
from .models import (
    OnboardingStatus,
    StudioDetails, StudioContact, StudioUSP, StudioMedia,
    ProductTypes, FabricAnswer, BrandExperience, AwardMention,
    CraftDetail, CollabDesign, BuyerRequirement,
    ProductionScale, MOQEntry,
    ProcessReadiness, BTSMedia,
)


@admin.register(OnboardingStatus)
class OnboardingStatusAdmin(admin.ModelAdmin):
    list_display  = ['seller_profile', 'completion_percentage', 'is_fully_submitted',
                     'section_a_status', 'section_b_status', 'section_c_status',
                     'section_d_status', 'section_e_status', 'section_f_status']
    list_filter   = ['is_fully_submitted', 'section_a_status']
    search_fields = ['seller_profile__profile_name']


@admin.register(StudioDetails)
class StudioDetailsAdmin(admin.ModelAdmin):
    list_display  = ['studio_name', 'seller_profile', 'location_city', 'is_flagged']
    list_filter   = ['is_flagged']
    search_fields = ['studio_name', 'seller_profile__profile_name']


@admin.register(StudioContact)
class StudioContactAdmin(admin.ModelAdmin):
    list_display  = ['name', 'role', 'email', 'studio', 'is_flagged']
    search_fields = ['name', 'email']


@admin.register(StudioUSP)
class StudioUSPAdmin(admin.ModelAdmin):
    list_display  = ['strength', 'order', 'studio', 'is_flagged']


@admin.register(StudioMedia)
class StudioMediaAdmin(admin.ModelAdmin):
    list_display  = ['file_name', 'media_type', 'studio', 'file_size_kb', 'is_flagged']
    list_filter   = ['media_type', 'is_flagged']


@admin.register(ProductTypes)
class ProductTypesAdmin(admin.ModelAdmin):
    list_display  = ['seller_profile', 'is_flagged']
    list_filter   = ['is_flagged']


@admin.register(FabricAnswer)
class FabricAnswerAdmin(admin.ModelAdmin):
    list_display  = ['fabric_name', 'category', 'works_with', 'is_primary', 'seller_profile', 'is_flagged']
    list_filter   = ['category', 'works_with', 'is_primary', 'is_flagged']
    search_fields = ['fabric_name']


@admin.register(BrandExperience)
class BrandExperienceAdmin(admin.ModelAdmin):
    list_display  = ['brand_name', 'seller_profile', 'order', 'is_flagged']
    search_fields = ['brand_name']


@admin.register(AwardMention)
class AwardMentionAdmin(admin.ModelAdmin):
    list_display  = ['award_name', 'seller_profile', 'order', 'is_flagged']
    search_fields = ['award_name']


@admin.register(CraftDetail)
class CraftDetailAdmin(admin.ModelAdmin):
    list_display  = ['craft_name', 'seller_profile', 'is_primary', 'innovation_level', 'is_flagged']
    list_filter   = ['is_primary', 'innovation_level', 'is_flagged']
    search_fields = ['craft_name']


@admin.register(CollabDesign)
class CollabDesignAdmin(admin.ModelAdmin):
    list_display  = ['seller_profile', 'has_fashion_designer', 'can_develop_from_references', 'is_flagged']
    list_filter   = ['has_fashion_designer', 'is_flagged']


@admin.register(BuyerRequirement)
class BuyerRequirementAdmin(admin.ModelAdmin):
    list_display  = ['question', 'order', 'collab', 'is_flagged']


@admin.register(ProductionScale)
class ProductionScaleAdmin(admin.ModelAdmin):
    list_display  = ['seller_profile', 'monthly_capacity_units', 'has_strict_minimums', 'is_flagged']
    list_filter   = ['has_strict_minimums', 'is_flagged']


@admin.register(MOQEntry)
class MOQEntryAdmin(admin.ModelAdmin):
    list_display  = ['craft_or_category', 'production_scale', 'order', 'is_flagged']


@admin.register(ProcessReadiness)
class ProcessReadinessAdmin(admin.ModelAdmin):
    list_display  = ['seller_profile', 'steps_flagged', 'is_flagged']
    list_filter   = ['is_flagged']


@admin.register(BTSMedia)
class BTSMediaAdmin(admin.ModelAdmin):
    list_display  = ['file_name', 'mime_type', 'file_size_kb', 'process_readiness', 'is_flagged']
    list_filter   = ['is_flagged']