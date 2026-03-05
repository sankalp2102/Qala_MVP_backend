# discovery/serializers.py
from rest_framework import serializers
from seller_profile.models import StudioMedia
from .models import (
    BuyerProfile, StudioRecommendation,
    CraftInterest, BatchSize, Timeline, ExperimentationChoice,
)


# ─────────────────────────────────────────────────────────────────────────────
# INPUT — Readiness Check
# ─────────────────────────────────────────────────────────────────────────────

class ReadinessCheckSerializer(serializers.Serializer):
    """
    Validates buyer questionnaire answers.
    All fields optional except product_types (Q2 requires >= 1).
    session_token is optional — if provided, resumes an existing BuyerProfile.
    """

    # Resume existing session
    session_token = serializers.UUIDField(required=False, allow_null=True)

    # Q9
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    last_name  = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')

    # Q1
    visual_selection_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )

    # Q2 — required, at least 1
    product_types = serializers.ListField(
        child=serializers.CharField(), min_length=1
    )

    # Q3
    fabrics            = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    fabric_is_flexible = serializers.BooleanField(required=False, default=False)
    fabric_not_sure    = serializers.BooleanField(required=False, default=False)

    # Q4
    craft_interest = serializers.ChoiceField(
        choices=[c[0] for c in CraftInterest.choices],
        required=False, allow_null=True, default=None
    )

    # Q4A
    crafts            = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    craft_is_flexible = serializers.BooleanField(required=False, default=False)
    craft_not_sure    = serializers.BooleanField(required=False, default=False)

    # Q4B
    experimentation = serializers.ChoiceField(
        choices=[c[0] for c in ExperimentationChoice.choices],
        required=False, default=ExperimentationChoice.SKIPPED
    )

    # Q5
    process_stage = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True, default=''
    )

    # Q6
    design_support = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    # Q7
    timeline = serializers.ChoiceField(
        choices=[c[0] for c in Timeline.choices],
        required=False, allow_null=True, default=None
    )

    # Q8
    batch_size = serializers.ChoiceField(
        choices=[c[0] for c in BatchSize.choices],
        required=False, allow_null=True, default=None
    )

    def validate_product_types(self, value):
        if not value:
            raise serializers.ValidationError("Please select at least one product type.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT — Q1 Visual Grid Images
# ─────────────────────────────────────────────────────────────────────────────

class VisualGridImageSerializer(serializers.ModelSerializer):
    studio_id   = serializers.IntegerField(source='studio.seller_profile_id')
    studio_name = serializers.SerializerMethodField()
    image_url   = serializers.SerializerMethodField()

    class Meta:
        model  = StudioMedia
        fields = ['id', 'studio_id', 'studio_name', 'image_url', 'caption']

    def get_studio_name(self, obj):
        return obj.studio.studio_name or ''

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT — Studio Recommendation Card
# ─────────────────────────────────────────────────────────────────────────────

class StudioRecommendationSerializer(serializers.ModelSerializer):
    studio_id          = serializers.IntegerField(source='seller_profile.id')
    studio_name        = serializers.SerializerMethodField()
    location           = serializers.SerializerMethodField()
    years_in_operation = serializers.SerializerMethodField()
    hero_images        = serializers.SerializerMethodField()
    primary_crafts     = serializers.SerializerMethodField()
    craft_profiles     = serializers.SerializerMethodField()

    class Meta:
        model  = StudioRecommendation
        fields = [
            'id',
            'studio_id',
            'studio_name',
            'location',
            'years_in_operation',
            'hero_images',
            'primary_crafts',
            'rank_position',
            'ranking',
            'core_capability_fit',
            'moq_fit',
            'craft_approach_fit',
            'visual_affinity',
            'match_reasoning',
            'what_best_at',
            'what_to_keep_in_mind',
            'is_bonus_visual',
            'selected_image_ids',
            'mismatches',
            'craft_profiles',
        ]

    def _studio_details(self, obj):
        try:
            return obj.seller_profile.studio_details
        except Exception:
            return None

    def get_studio_name(self, obj):
        sd = self._studio_details(obj)
        return sd.studio_name if sd else None

    def get_location(self, obj):
        sd = self._studio_details(obj)
        if not sd:
            return None
        parts = [p for p in [sd.location_city, sd.location_state] if p]
        return ', '.join(parts) if parts else None

    def get_years_in_operation(self, obj):
        sd = self._studio_details(obj)
        return sd.years_in_operation if sd else None

    def get_hero_images(self, obj):
        """Up to 8 images for the card gallery (hero + work_dump)."""
        request = self.context.get('request')
        media   = StudioMedia.objects.filter(
            studio__seller_profile=obj.seller_profile,
            media_type__in=[
                StudioMedia.MediaType.HERO,
                StudioMedia.MediaType.WORK_DUMP,
            ],
        ).order_by('media_type', 'order')[:8]

        return [
            {
                'id':          m.id,
                'url':         request.build_absolute_uri(m.file.url) if m.file and request else None,
                'caption':     m.caption,
                'media_type':  m.media_type,
                'is_selected': m.id in (obj.selected_image_ids or []),
            }
            for m in media
        ]

    def get_primary_crafts(self, obj):
        return list(
            obj.seller_profile.crafts
            .filter(is_primary=True)
            .values_list('craft_name', flat=True)[:5]
        )

    def get_craft_profiles(self, obj):
        """Detailed per-craft data shown on the studio card."""
        request = self.context.get('request')
        result  = []
        for c in obj.seller_profile.crafts.all().order_by('-is_primary', 'order'):
            result.append({
                'craft_name':           c.craft_name,
                'primary_or_secondary': 'primary' if c.is_primary else 'secondary',
                'specialization':       c.specialization,
                'sampling_time':        f"{c.sampling_time_weeks} weeks" if c.sampling_time_weeks else None,
                'production_timeline':  (
                    f"{c.production_timeline_months_50units} months (50 units)"
                    if c.production_timeline_months_50units else None
                ),
                'limitations':          c.limitations,
                'innovation_level':     c.innovation_level,
                'image_url':            (
                    request.build_absolute_uri(c.image.url)
                    if c.image and request else None
                ),
            })
        return result


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT — Buyer Profile Summary (for context strip + session restore)
# ─────────────────────────────────────────────────────────────────────────────

class BuyerProfileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model  = BuyerProfile
        fields = [
            'id', 'session_token',
            'first_name', 'last_name',
            'visual_selection_ids',
            'product_types',
            'fabrics', 'fabric_is_flexible', 'fabric_not_sure',
            'craft_interest', 'crafts', 'craft_is_flexible', 'craft_not_sure',
            'experimentation',
            'process_stage',
            'design_support',
            'timeline',
            'batch_size',
            'journey_stage',
            'matching_complete',
            'zero_match_suggestions',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields  # summary is always read-only