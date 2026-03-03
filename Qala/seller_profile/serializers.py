# seller_profile/serializers.py
import magic
from rest_framework import serializers
from .models import (
    OnboardingStatus, SectionStatus,
    StudioDetails, StudioContact, StudioUSP, StudioMedia,
    ProductTypes, FabricAnswer, BrandExperience, AwardMention,
    CraftDetail, CollabDesign, BuyerRequirement,
    ProductionScale, MOQEntry,
    ProcessReadiness, BTSMedia,
)

# ─────────────────────────────────────────────────────────────────────────────
# FILE VALIDATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/quicktime', 'video/x-msvideo'}
ALLOWED_MEDIA_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES

MAX_IMAGE_MB = 10
MAX_VIDEO_MB = 100


def detect_mime(file) -> str:
    """Read first 2KB to detect real MIME type (ignores client Content-Type)."""
    header = file.read(2048)
    file.seek(0)
    return magic.from_buffer(header, mime=True)


def validate_file(file, allowed: set, max_mb: int):
    mime = detect_mime(file)
    if mime not in allowed:
        raise serializers.ValidationError(
            f'Unsupported file type "{mime}". Allowed: {", ".join(sorted(allowed))}'
        )
    if file.size > max_mb * 1024 * 1024:
        raise serializers.ValidationError(f'File exceeds {max_mb} MB limit.')
    return file, mime


def auto_fill_file_meta(validated_data: dict, file_field: str = 'file') -> dict:
    """Populate file_name, mime_type, file_size_kb automatically from the upload."""
    f = validated_data.get(file_field)
    if f:
        validated_data['file_name']    = f.name
        validated_data['mime_type']    = detect_mime(f)
        validated_data['file_size_kb'] = max(1, f.size // 1024)
    return validated_data


# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING STATUS
# ─────────────────────────────────────────────────────────────────────────────
class OnboardingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OnboardingStatus
        fields = [
            'section_a_status', 'section_b_status', 'section_c_status',
            'section_d_status', 'section_e_status', 'section_f_status',
            'completion_percentage', 'is_fully_submitted',
            'admin_reviewed', 'admin_notes',
            'last_saved_at', 'submitted_at',
        ]
        read_only_fields = [
            'completion_percentage', 'is_fully_submitted',
            'submitted_at', 'admin_reviewed', 'admin_notes',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION A
# ─────────────────────────────────────────────────────────────────────────────
class StudioContactSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudioContact
        fields = ['id', 'name', 'role', 'email', 'phone', 'order',
                  'is_flagged', 'flag_reason', 'flag_resolved']
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


class StudioUSPSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudioUSP
        fields = ['id', 'order', 'strength',
                  'is_flagged', 'flag_reason', 'flag_resolved']
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


class StudioMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudioMedia
        fields = [
            'id', 'media_type', 'file', 'file_name',
            'mime_type', 'file_size_kb', 'caption', 'order', 'uploaded_at',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]
        read_only_fields = [
            'id', 'file_name', 'mime_type', 'file_size_kb', 'uploaded_at',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]

    def validate_file(self, file):
        validated, _ = validate_file(file, ALLOWED_MEDIA_TYPES, MAX_VIDEO_MB)
        return validated

    def create(self, validated_data):
        return super().create(auto_fill_file_meta(validated_data))


class StudioDetailsSerializer(serializers.ModelSerializer):
    contacts    = StudioContactSerializer(many=True, read_only=True)
    usps        = StudioUSPSerializer(many=True, read_only=True)
    media_files = StudioMediaSerializer(many=True, read_only=True)

    class Meta:
        model  = StudioDetails
        fields = [
            # Core fields
            'id', 'studio_name', 'location_city', 'location_state',
            'years_in_operation', 'website_url', 'instagram_url', 'poc_working_style',
            # Per-field flags (read-only for seller; writable only by admin)
            'studio_name_flagged', 'studio_name_flag_reason',
            'location_flagged',    'location_flag_reason',
            'years_flagged',       'years_flag_reason',
            'website_flagged',     'website_flag_reason',
            'poc_flagged',         'poc_flag_reason',
            # Row-level flag
            'is_flagged', 'flag_reason', 'flag_resolved',
            # Nested children
            'contacts', 'usps', 'media_files',
        ]
        read_only_fields = [
            'id',
            'studio_name_flagged', 'studio_name_flag_reason',
            'location_flagged',    'location_flag_reason',
            'years_flagged',       'years_flag_reason',
            'website_flagged',     'website_flag_reason',
            'poc_flagged',         'poc_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B
# ─────────────────────────────────────────────────────────────────────────────
class ProductTypesSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProductTypes
        fields = [
            'id',
            'dresses', 'tops', 'shirts', 't_shirts', 'tunics_kurtas',
            'coord_sets', 'jumpsuits', 'skirts', 'shorts', 'trousers_pants',
            'denim', 'blazers', 'coats_jackets', 'capes', 'waistcoats_vests',
            'kaftans', 'resortwear_sets', 'loungewear_sleepwear', 'activewear',
            'kidswear', 'accessories_scarves_stoles',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


class FabricAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FabricAnswer
        fields = [
            'id', 'category', 'fabric_name', 'works_with',
            'innovation_note', 'is_primary',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


class FabricAnswerBulkSerializer(serializers.Serializer):
    """
    Accepts a list of fabric answers and upserts them in bulk.
    PUT /api/seller/onboarding/fabrics/
    """
    fabrics = FabricAnswerSerializer(many=True)

    def update(self, seller_profile, validated_data):
        for fabric_data in validated_data['fabrics']:
            FabricAnswer.objects.update_or_create(
                seller_profile=seller_profile,
                fabric_name=fabric_data['fabric_name'],
                defaults={
                    'category':        fabric_data.get('category'),
                    'works_with':      fabric_data.get('works_with', False),
                    'innovation_note': fabric_data.get('innovation_note'),
                    'is_primary':      fabric_data.get('is_primary'),
                },
            )
        return seller_profile


class BrandExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BrandExperience
        fields = [
            'id', 'brand_name', 'scope', 'image',
            'file_name', 'mime_type', 'file_size_kb', 'order',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]
        read_only_fields = [
            'id', 'file_name', 'mime_type', 'file_size_kb',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]

    def validate_image(self, file):
        if file:
            validated, _ = validate_file(file, ALLOWED_IMAGE_TYPES, MAX_IMAGE_MB)
            return validated
        return file

    def create(self, validated_data):
        return super().create(auto_fill_file_meta(validated_data))

    def update(self, instance, validated_data):
        auto_fill_file_meta(validated_data)
        return super().update(instance, validated_data)


class AwardMentionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AwardMention
        fields = ['id', 'award_name', 'link', 'order',
                  'is_flagged', 'flag_reason', 'flag_resolved']
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


# ─────────────────────────────────────────────────────────────────────────────
# SECTION C
# ─────────────────────────────────────────────────────────────────────────────
class CraftDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CraftDetail
        fields = [
            'id', 'craft_name', 'specialization', 'is_primary',
            'innovation_level', 'limitations',
            'sampling_time_weeks', 'production_timeline_months_50units',
            'delay_likelihood', 'delay_common_reasons',
            'image', 'file_name', 'mime_type', 'file_size_kb', 'order',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]
        read_only_fields = [
            'id', 'file_name', 'mime_type', 'file_size_kb',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]

    def validate_image(self, file):
        if file:
            validated, _ = validate_file(file, ALLOWED_IMAGE_TYPES, MAX_IMAGE_MB)
            return validated
        return file

    def create(self, validated_data):
        return super().create(auto_fill_file_meta(validated_data))

    def update(self, instance, validated_data):
        auto_fill_file_meta(validated_data)
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION D
# ─────────────────────────────────────────────────────────────────────────────
class BuyerRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BuyerRequirement
        fields = ['id', 'order', 'question',
                  'is_flagged', 'flag_reason', 'flag_resolved']
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


class CollabDesignSerializer(serializers.ModelSerializer):
    buyer_requirements = BuyerRequirementSerializer(many=True, read_only=True)

    class Meta:
        model  = CollabDesign
        fields = [
            'id',
            'has_fashion_designer', 'can_develop_from_references', 'max_sampling_iterations',
            'designer_flagged',   'designer_flag_reason',
            'references_flagged', 'references_flag_reason',
            'iterations_flagged', 'iterations_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
            'buyer_requirements',
        ]
        read_only_fields = [
            'id',
            'designer_flagged',   'designer_flag_reason',
            'references_flagged', 'references_flag_reason',
            'iterations_flagged', 'iterations_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION E
# ─────────────────────────────────────────────────────────────────────────────
class MOQEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = MOQEntry
        fields = ['id', 'craft_or_category', 'moq_condition', 'order',
                  'is_flagged', 'flag_reason', 'flag_resolved']
        read_only_fields = ['id', 'is_flagged', 'flag_reason', 'flag_resolved']


class ProductionScaleSerializer(serializers.ModelSerializer):
    moq_entries = MOQEntrySerializer(many=True, read_only=True)

    class Meta:
        model  = ProductionScale
        fields = [
            'id', 'monthly_capacity_units', 'has_strict_minimums',
            'capacity_flagged',  'capacity_flag_reason',
            'minimums_flagged',  'minimums_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
            'moq_entries',
        ]
        read_only_fields = [
            'id',
            'capacity_flagged',  'capacity_flag_reason',
            'minimums_flagged',  'minimums_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION F
# ─────────────────────────────────────────────────────────────────────────────
class BTSMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BTSMedia
        fields = [
            'id', 'file', 'file_name', 'mime_type', 'file_size_kb',
            'caption', 'order', 'uploaded_at',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]
        read_only_fields = [
            'id', 'file_name', 'mime_type', 'file_size_kb', 'uploaded_at',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]

    def validate_file(self, file):
        validated, _ = validate_file(file, ALLOWED_MEDIA_TYPES, MAX_VIDEO_MB)
        return validated

    def create(self, validated_data):
        return super().create(auto_fill_file_meta(validated_data))


class ProcessReadinessSerializer(serializers.ModelSerializer):
    bts_media = BTSMediaSerializer(many=True, read_only=True)

    class Meta:
        model  = ProcessReadiness
        fields = [
            'id', 'production_steps',
            'steps_flagged', 'steps_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
            'bts_media',
        ]
        read_only_fields = [
            'id',
            'steps_flagged', 'steps_flag_reason',
            'is_flagged', 'flag_reason', 'flag_resolved',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN FLAG SERIALIZERS  — used in admin-only flag + resolve endpoints
# ─────────────────────────────────────────────────────────────────────────────
class AdminFlagSerializer(serializers.Serializer):
    """
    POST /api/admin/seller-profiles/<profile_id>/flag/
    Body: { model, field, reason }
    field is optional — if omitted, flags the whole model row.
    """
    model  = serializers.ChoiceField(choices=[
        'studio_details', 'product_types', 'craft',
        'collab_design', 'production_scale', 'process_readiness',
        'fabric_answer', 'brand_experience', 'award_mention',
        'studio_contact', 'studio_usp', 'studio_media',
        'moq_entry', 'buyer_requirement', 'bts_media',
    ])
    object_id = serializers.IntegerField(
        required=False,
        help_text='Required for child-row models (craft, fabric_answer, etc.)'
    )
    field  = serializers.CharField(
        required=False, allow_blank=True,
        help_text='Specific field name to flag (e.g. studio_name). Leave blank to flag the whole row.'
    )
    reason = serializers.CharField(max_length=1000)


class AdminResolveFlagSerializer(serializers.Serializer):
    """
    POST /api/admin/seller-profiles/<profile_id>/resolve-flag/
    Body: { model, object_id, field }
    """
    model     = AdminFlagSerializer().fields['model']
    object_id = serializers.IntegerField(required=False)
    field     = serializers.CharField(required=False, allow_blank=True)


# ─────────────────────────────────────────────────────────────────────────────
# FULL ONBOARDING READ SERIALIZER  — GET /api/seller/onboarding/
# ─────────────────────────────────────────────────────────────────────────────
class FullOnboardingSerializer(serializers.Serializer):
    """
    Read-only aggregator. Returns the complete onboarding snapshot
    for a SellerProfile in one API call — used to hydrate the seller dashboard.
    """
    status             = serializers.SerializerMethodField()
    studio_details     = serializers.SerializerMethodField()
    product_types      = serializers.SerializerMethodField()
    fabric_answers     = serializers.SerializerMethodField()
    brand_experiences  = serializers.SerializerMethodField()
    awards             = serializers.SerializerMethodField()
    crafts             = serializers.SerializerMethodField()
    collab_design      = serializers.SerializerMethodField()
    production_scale   = serializers.SerializerMethodField()
    process_readiness  = serializers.SerializerMethodField()

    def _try(self, fn):
        try:
            return fn()
        except Exception:
            return None

    def get_status(self, profile):
        return self._try(lambda: OnboardingStatusSerializer(profile.onboarding_status).data)

    def get_studio_details(self, profile):
        return self._try(lambda: StudioDetailsSerializer(profile.studio_details).data)

    def get_product_types(self, profile):
        return self._try(lambda: ProductTypesSerializer(profile.product_types).data)

    def get_fabric_answers(self, profile):
        return FabricAnswerSerializer(profile.fabric_answers.all(), many=True).data

    def get_brand_experiences(self, profile):
        return BrandExperienceSerializer(profile.brand_experiences.all(), many=True).data

    def get_awards(self, profile):
        return AwardMentionSerializer(profile.awards.all(), many=True).data

    def get_crafts(self, profile):
        return CraftDetailSerializer(profile.crafts.all(), many=True).data

    def get_collab_design(self, profile):
        return self._try(lambda: CollabDesignSerializer(profile.collab_design).data)

    def get_production_scale(self, profile):
        return self._try(lambda: ProductionScaleSerializer(profile.production_scale).data)

    def get_process_readiness(self, profile):
        return self._try(lambda: ProcessReadinessSerializer(profile.process_readiness).data)