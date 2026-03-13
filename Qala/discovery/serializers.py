# discovery/serializers.py
from rest_framework import serializers
from seller_profile.models import StudioMedia
from .models import (
    BuyerProfile, StudioRecommendation, StudioInquiry,
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

# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC STUDIO PROFILE — buyer-facing read-only, no internal flags exposed
# ─────────────────────────────────────────────────────────────────────────────

class PublicStudioProfileSerializer(serializers.Serializer):
    """
    Assembles all public data for a verified studio into a single flat response.
    Called by GET /api/discovery/studios/<profile_id>/
    """

    studio_id          = serializers.SerializerMethodField()
    studio_name        = serializers.SerializerMethodField()
    location_city      = serializers.SerializerMethodField()
    location_state     = serializers.SerializerMethodField()
    years_in_operation = serializers.SerializerMethodField()
    website_url        = serializers.SerializerMethodField()
    instagram_url      = serializers.SerializerMethodField()
    poc_working_style  = serializers.SerializerMethodField()

    hero_image  = serializers.SerializerMethodField()
    work_images = serializers.SerializerMethodField()
    bts_images  = serializers.SerializerMethodField()

    usps             = serializers.SerializerMethodField()
    product_types    = serializers.SerializerMethodField()
    crafts           = serializers.SerializerMethodField()
    fabrics          = serializers.SerializerMethodField()
    brands           = serializers.SerializerMethodField()
    awards           = serializers.SerializerMethodField()
    contacts         = serializers.SerializerMethodField()
    production       = serializers.SerializerMethodField()
    pre_call_questions = serializers.SerializerMethodField()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _sd(self, profile):
        """Safely return StudioDetails or None."""
        try:
            return profile.studio_details
        except Exception:
            return None

    def _req(self):
        return self.context.get('request')

    def _media_url(self, media_obj):
        req = self._req()
        if media_obj.file and req:
            return req.build_absolute_uri(media_obj.file.url)
        return None

    # ── fields ───────────────────────────────────────────────────────────────

    def get_studio_id(self, profile):
        return profile.id

    def get_studio_name(self, profile):
        sd = self._sd(profile)
        return sd.studio_name if sd else None

    def get_location_city(self, profile):
        sd = self._sd(profile)
        return sd.location_city if sd else None

    def get_location_state(self, profile):
        sd = self._sd(profile)
        return sd.location_state if sd else None

    def get_years_in_operation(self, profile):
        sd = self._sd(profile)
        return sd.years_in_operation if sd else None

    def get_website_url(self, profile):
        sd = self._sd(profile)
        return sd.website_url if sd else None

    def get_instagram_url(self, profile):
        sd = self._sd(profile)
        return sd.instagram_url if sd else None

    def get_poc_working_style(self, profile):
        sd = self._sd(profile)
        return sd.poc_working_style if sd else None

    def get_hero_image(self, profile):
        sd = self._sd(profile)
        if not sd:
            return None
        hero = sd.media_files.filter(
            media_type=StudioMedia.MediaType.HERO
        ).first()
        if not hero:
            return None
        return {'url': self._media_url(hero), 'caption': hero.caption}

    def get_work_images(self, profile):
        sd = self._sd(profile)
        if not sd:
            return []
        images = sd.media_files.filter(
            media_type=StudioMedia.MediaType.WORK_DUMP
        ).order_by('order')
        return [
            {'id': m.id, 'url': self._media_url(m), 'caption': m.caption}
            for m in images
        ]

    def get_bts_images(self, profile):
        try:
            pr = profile.process_readiness
        except Exception:
            return []
        return [
            {'id': m.id, 'url': self._media_url(m), 'caption': m.caption}
            for m in pr.bts_media.order_by('order')
        ]

    def get_usps(self, profile):
        sd = self._sd(profile)
        if not sd:
            return []
        return [u.strength for u in sd.usps.order_by('order')]

    def get_product_types(self, profile):
        """Return list of field names where value is True."""
        try:
            pt = profile.product_types
        except Exception:
            return []
        boolean_fields = [
            'dresses', 'tops', 'shirts', 't_shirts', 'tunics_kurtas',
            'coord_sets', 'jumpsuits', 'skirts', 'shorts', 'trousers_pants',
            'denim', 'blazers', 'coats_jackets', 'capes', 'waistcoats_vests',
            'kaftans', 'resortwear_sets', 'loungewear_sleepwear', 'activewear',
            'kidswear', 'accessories_scarves_stoles',
        ]
        return [f for f in boolean_fields if getattr(pt, f, False)]

    def get_crafts(self, profile):
        req = self._req()
        result = []
        for c in profile.crafts.all().order_by('-is_primary', 'order'):
            result.append({
                'id':                              c.id,
                'craft_name':                      c.craft_name,
                'is_primary':                      c.is_primary,
                'specialization':                  c.specialization,
                'innovation_level':                c.innovation_level,
                'sampling_time_weeks':             c.sampling_time_weeks,
                'production_timeline_months_50units': c.production_timeline_months_50units,
                'limitations':                     c.limitations,
                'delay_likelihood':                c.delay_likelihood,
                'image_url': (
                    req.build_absolute_uri(c.image.url)
                    if c.image and req else None
                ),
            })
        return result

    def get_fabrics(self, profile):
        fabrics = profile.fabric_answers.filter(works_with=True).order_by('category', 'fabric_name')
        return [
            {
                'fabric_name': f.fabric_name,
                'category':    f.category,
                'is_primary':  f.is_primary,
            }
            for f in fabrics
        ]

    def get_brands(self, profile):
        req = self._req()
        result = []
        for b in profile.brand_experiences.order_by('order'):
            image_url = None
            if b.image and req:
                image_url = req.build_absolute_uri(b.image.url)
            result.append({
                'brand_name': b.brand_name,
                'scope':      b.scope,
                'image_url':  image_url,
            })
        return result

    def get_awards(self, profile):
        return [
            {'award_name': a.award_name, 'link': a.link}
            for a in profile.awards.order_by('order')
        ]

    def get_contacts(self, profile):
        sd = self._sd(profile)
        if not sd:
            return []
        return [
            {
                'name':  c.name,
                'role':  c.role,
                'email': c.email,
                'phone': c.phone,
            }
            for c in sd.contacts.order_by('order')
        ]

    def get_production(self, profile):
        try:
            ps = profile.production_scale
        except Exception:
            return None
        return {
            'monthly_capacity_units': ps.monthly_capacity_units,
            'has_strict_minimums':    ps.has_strict_minimums,
            'moq_entries': [
                {
                    'craft_or_category': m.craft_or_category,
                    'moq_condition':     m.moq_condition,
                }
                for m in ps.moq_entries.order_by('order')
            ],
        }

    def get_pre_call_questions(self, profile):
        try:
            collab = profile.collab_design
        except Exception:
            return []
        return [
            {'order': r.order, 'question': r.question}
            for r in collab.buyer_requirements.order_by('order')
        ]



# ─────────────────────────────────────────────────────────────────────────────
# STUDIO DIRECTORY — public card data for Feature 6
# ─────────────────────────────────────────────────────────────────────────────

# Maps craft name keywords → CSS pattern class used on the directory card visual
_CRAFT_PATTERN_MAP = {
    'block': 'pattern-block',
    'print': 'pattern-print',
    'embroidery': 'pattern-embroidery',
    'kantha': 'pattern-embroidery',
    'zardozi': 'pattern-embroidery',
    'chikankari': 'pattern-embroidery',
    'handloom': 'pattern-weave',
    'weav': 'pattern-weave',
    'loom': 'pattern-weave',
    'banarasi': 'pattern-weave',
    'dye': 'pattern-dye',
    'indigo': 'pattern-dye',
    'shibori': 'pattern-dye',
    'leather': 'pattern-leather',
}


def _craft_to_pattern(craft_name: str) -> str:
    """Return CSS pattern class for a given craft name."""
    lower = (craft_name or '').lower()
    for keyword, pattern in _CRAFT_PATTERN_MAP.items():
        if keyword in lower:
            return pattern
    return 'pattern-block'  # safe default


def _sampling_time_display(weeks) -> str | None:
    """Convert float weeks to human display, e.g. 2.5 → '2-3 weeks'."""
    if weeks is None:
        return None
    w = float(weeks)
    lo = int(w)
    hi = lo + 1
    if w == lo:
        return f'{lo} weeks'
    return f'{lo}-{hi} weeks'


class StudioDirectorySerializer(serializers.Serializer):
    """
    Lightweight read-only card data for the Studio Directory (Feature 6).
    Called by GET /api/studios/directory/ for each SellerProfile in the result set.
    """
    studio_id                     = serializers.SerializerMethodField()
    studio_name                   = serializers.SerializerMethodField()
    location                      = serializers.SerializerMethodField()
    years_in_operation            = serializers.SerializerMethodField()
    short_description             = serializers.SerializerMethodField()
    hero_image_url                = serializers.SerializerMethodField()
    primary_craft                 = serializers.SerializerMethodField()
    secondary_crafts              = serializers.SerializerMethodField()
    fabrics                       = serializers.SerializerMethodField()
    product_types                 = serializers.SerializerMethodField()
    has_inhouse_designer          = serializers.SerializerMethodField()
    typical_sampling_time_display = serializers.SerializerMethodField()
    card_pattern                  = serializers.SerializerMethodField()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _sd(self, profile):
        try:
            return profile.studio_details
        except Exception:
            return None

    # ── fields ───────────────────────────────────────────────────────────────

    def get_studio_id(self, profile):
        return profile.id

    def get_studio_name(self, profile):
        sd = self._sd(profile)
        return sd.studio_name if sd else None

    def get_location(self, profile):
        sd = self._sd(profile)
        if not sd:
            return None
        parts = [p for p in [sd.location_city, sd.location_state] if p]
        return ', '.join(parts) if parts else None

    def get_years_in_operation(self, profile):
        sd = self._sd(profile)
        return sd.years_in_operation if sd else None

    def get_short_description(self, profile):
        sd = self._sd(profile)
        return sd.short_description if sd else None

    def get_hero_image_url(self, profile):
        sd = self._sd(profile)
        if not sd:
            return None
        # Try hero type first, fall back to first work_dump image
        hero = sd.media_files.filter(
            media_type=StudioMedia.MediaType.HERO
        ).first()
        if not hero:
            hero = sd.media_files.filter(
                media_type=StudioMedia.MediaType.WORK_DUMP
            ).order_by('order').first()
        if not hero or not hero.file:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(hero.file.url)
        # Fallback: return relative URL, frontend will prepend base
        return hero.file.url

    def get_primary_craft(self, profile):
        craft = profile.crafts.filter(is_primary=True).first()
        return craft.craft_name if craft else None

    def get_secondary_crafts(self, profile):
        return list(
            profile.crafts.filter(is_primary=False)
            .values_list('craft_name', flat=True)[:4]
        )

    def get_fabrics(self, profile):
        return list(
            profile.fabric_answers.filter(works_with=True)
            .values_list('fabric_name', flat=True)
            .order_by('fabric_name')
        )

    def get_product_types(self, profile):
        _BOOLEAN_FIELDS = [
            'dresses', 'tops', 'shirts', 't_shirts', 'tunics_kurtas',
            'coord_sets', 'jumpsuits', 'skirts', 'shorts', 'trousers_pants',
            'denim', 'blazers', 'coats_jackets', 'capes', 'waistcoats_vests',
            'kaftans', 'resortwear_sets', 'loungewear_sleepwear', 'activewear',
            'kidswear', 'accessories_scarves_stoles',
        ]
        try:
            pt = profile.product_types
        except Exception:
            return []
        return [f for f in _BOOLEAN_FIELDS if getattr(pt, f, False)]

    def get_has_inhouse_designer(self, profile):
        try:
            return profile.collab_design.has_fashion_designer
        except Exception:
            return None

    def get_typical_sampling_time_display(self, profile):
        crafts = profile.crafts.filter(is_primary=True, sampling_time_weeks__isnull=False)
        weeks_values = list(crafts.values_list('sampling_time_weeks', flat=True))
        if not weeks_values:
            all_crafts = profile.crafts.filter(sampling_time_weeks__isnull=False)
            weeks_values = list(all_crafts.values_list('sampling_time_weeks', flat=True))
        if not weeks_values:
            return None
        return _sampling_time_display(min(weeks_values))

    def get_card_pattern(self, profile):
        craft = profile.crafts.filter(is_primary=True).first()
        return _craft_to_pattern(craft.craft_name if craft else '')


class StudioInquirySerializer(serializers.Serializer):
    name          = serializers.CharField(max_length=200)
    email         = serializers.EmailField()
    answers       = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField(allow_blank=True)),
        required=False,
        default=list,
    )
    session_token = serializers.UUIDField(required=False, allow_null=True)
    