# seller_profile/models.py
from django.db import models
from django.utils import timezone
from core.models import User, SellerProfile


# ─────────────────────────────────────────────────────────────────────────────
# ABSTRACT MIXIN — gives every answer model admin-flag capability
# ─────────────────────────────────────────────────────────────────────────────
class FlagMixin(models.Model):
    """
    Inherit this on any model that admin should be able to flag.
    Provides: is_flagged, flag_reason, flagged_by, flagged_at, flag_resolved.
    """
    is_flagged    = models.BooleanField(default=False)
    flag_reason   = models.TextField(null=True, blank=True)
    flagged_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(class)s_flags'
    )
    flagged_at    = models.DateTimeField(null=True, blank=True)
    flag_resolved = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def apply_flag(self, admin_user, reason: str):
        self.is_flagged    = True
        self.flag_reason   = reason
        self.flagged_by    = admin_user
        self.flagged_at    = timezone.now()
        self.flag_resolved = False
        self.save(update_fields=['is_flagged', 'flag_reason', 'flagged_by', 'flagged_at', 'flag_resolved'])

    def resolve_flag(self):
        self.is_flagged    = False
        self.flag_resolved = True
        self.flagged_at    = None
        self.save(update_fields=['is_flagged', 'flag_resolved', 'flagged_at'])


# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING STATUS — tracks section-level progress per SellerProfile
# ─────────────────────────────────────────────────────────────────────────────
class SectionStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    IN_PROGRESS = 'in_progress', 'In Progress'
    SUBMITTED   = 'submitted',   'Submitted'
    FLAGGED     = 'flagged',     'Flagged by Admin'
    APPROVED    = 'approved',    'Approved'


class OnboardingStatus(models.Model):
    """
    One row per SellerProfile. Tracks per-section status + overall completion %.
    Admin notes go here. Seller sees this on their dashboard.
    """
    seller_profile    = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='onboarding_status')

    section_a_status  = models.CharField(max_length=20, choices=SectionStatus.choices, default=SectionStatus.NOT_STARTED)
    section_b_status  = models.CharField(max_length=20, choices=SectionStatus.choices, default=SectionStatus.NOT_STARTED)
    section_c_status  = models.CharField(max_length=20, choices=SectionStatus.choices, default=SectionStatus.NOT_STARTED)
    section_d_status  = models.CharField(max_length=20, choices=SectionStatus.choices, default=SectionStatus.NOT_STARTED)
    section_e_status  = models.CharField(max_length=20, choices=SectionStatus.choices, default=SectionStatus.NOT_STARTED)
    section_f_status  = models.CharField(max_length=20, choices=SectionStatus.choices, default=SectionStatus.NOT_STARTED)

    completion_percentage = models.FloatField(default=0.0)
    is_fully_submitted    = models.BooleanField(default=False)

    admin_reviewed  = models.BooleanField(default=False)
    admin_notes     = models.TextField(null=True, blank=True)

    last_saved_at   = models.DateTimeField(null=True, blank=True)
    submitted_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'onboarding_status'

    def recalculate_completion(self):
        done_states = {SectionStatus.SUBMITTED, SectionStatus.APPROVED}
        sections    = [
            self.section_a_status, self.section_b_status,
            self.section_c_status, self.section_d_status,
            self.section_e_status, self.section_f_status,
        ]
        completed                 = sum(1 for s in sections if s in done_states)
        self.completion_percentage = round((completed / 6) * 100, 1)
        self.is_fully_submitted    = completed == 6
        self.save(update_fields=['completion_percentage', 'is_fully_submitted'])

    def flag_section(self, section_letter: str):
        field = f'section_{section_letter.lower()}_status'
        if hasattr(self, field):
            setattr(self, field, SectionStatus.FLAGGED)
            self.save(update_fields=[field])

    def __str__(self):
        return f'Onboarding {self.seller_profile} — {self.completion_percentage}%'


# ─────────────────────────────────────────────────────────────────────────────
# SECTION A — Studio Details
# ─────────────────────────────────────────────────────────────────────────────
class StudioDetails(FlagMixin):
    """
    A.1 Studio name  A.2 Location  A.3 Years  A.4 Website  A.5 Instagram
    A.6 → StudioContact (child)   A.7 → StudioUSP (child)
    A.8/9 → StudioMedia (child, direct file upload)
    POC working style (how seller prefers to work with buyers) also lives here.
    Each editable field has its own flag pair for granular admin flagging.
    """
    seller_profile   = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='studio_details')

    studio_name        = models.CharField(max_length=300, null=True, blank=True)
    location_city      = models.CharField(max_length=200, null=True, blank=True)
    location_state     = models.CharField(max_length=200, null=True, blank=True)
    years_in_operation = models.FloatField(null=True, blank=True)
    website_url        = models.URLField(null=True, blank=True)
    instagram_url      = models.URLField(null=True, blank=True)
    poc_working_style  = models.TextField(null=True, blank=True)  # A.5 — buyer POC style

    # Directory card blurb — written by Qala admin, not seller
    short_description = models.TextField(null=True, blank=True)

    # Per-field flags (admin can flag individual answers, not just the whole section)
    studio_name_flagged      = models.BooleanField(default=False)
    studio_name_flag_reason  = models.TextField(null=True, blank=True)

    location_flagged         = models.BooleanField(default=False)
    location_flag_reason     = models.TextField(null=True, blank=True)

    years_flagged            = models.BooleanField(default=False)
    years_flag_reason        = models.TextField(null=True, blank=True)

    website_flagged          = models.BooleanField(default=False)
    website_flag_reason      = models.TextField(null=True, blank=True)

    poc_flagged              = models.BooleanField(default=False)
    poc_flag_reason          = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'studio_details'

    def __str__(self):
        return f'StudioDetails: {self.studio_name}'


class StudioContact(FlagMixin):
    """A.6 — Multiple POC contacts per studio (+ Add Contact button)"""
    studio = models.ForeignKey(StudioDetails, on_delete=models.CASCADE, related_name='contacts')
    name   = models.CharField(max_length=200)
    role   = models.CharField(max_length=200)
    email  = models.EmailField(null=True, blank=True)
    phone  = models.CharField(max_length=30, null=True, blank=True)
    order  = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'studio_contacts'
        ordering = ['order']


class StudioUSP(FlagMixin):
    """A.7 — Up to 5 Strengths / USP rows"""
    studio   = models.ForeignKey(StudioDetails, on_delete=models.CASCADE, related_name='usps')
    order    = models.PositiveIntegerField()   # 1–5
    strength = models.TextField()

    class Meta:
        db_table        = 'studio_usps'
        ordering        = ['order']
        unique_together = [['studio', 'order']]


def studio_media_upload_path(instance, filename):
    return f'sellers/{instance.studio.seller_profile_id}/studio/{filename}'


class StudioMedia(FlagMixin):
    """
    A.8 Hero image  +  A.9 Work dump images/videos.
    Files are stored directly (no Drive link). mime_type + file_size_kb
    are populated automatically in the serializer's create().
    """
    class MediaType(models.TextChoices):
        HERO      = 'hero',      'Hero Image'
        WORK_DUMP = 'work_dump', 'Work Dump'
        BTS       = 'bts',       'Behind The Scenes'

    studio      = models.ForeignKey(StudioDetails, on_delete=models.CASCADE, related_name='media_files')
    media_type  = models.CharField(max_length=20, choices=MediaType.choices)
    file        = models.FileField(upload_to=studio_media_upload_path)
    file_name   = models.CharField(max_length=255)
    mime_type   = models.CharField(max_length=100)
    file_size_kb = models.IntegerField()
    caption     = models.CharField(max_length=300, null=True, blank=True)
    order       = models.PositiveIntegerField(default=1)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'studio_media'
        ordering = ['media_type', 'order']


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B — Product Types, Fabrics, Brand Experience, Awards
# ─────────────────────────────────────────────────────────────────────────────
class ProductTypes(FlagMixin):
    """
    B.1 — 21 garment silhouette booleans. One row per SellerProfile.
    These are direct ML filter signals for the recommendation engine.
    """
    seller_profile            = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='product_types')

    dresses                   = models.BooleanField(default=False)
    tops                      = models.BooleanField(default=False)
    shirts                    = models.BooleanField(default=False)
    t_shirts                  = models.BooleanField(default=False)
    tunics_kurtas             = models.BooleanField(default=False)
    coord_sets                = models.BooleanField(default=False)
    jumpsuits                 = models.BooleanField(default=False)
    skirts                    = models.BooleanField(default=False)
    shorts                    = models.BooleanField(default=False)
    trousers_pants            = models.BooleanField(default=False)
    denim                     = models.BooleanField(default=False)
    blazers                   = models.BooleanField(default=False)
    coats_jackets             = models.BooleanField(default=False)
    capes                     = models.BooleanField(default=False)
    waistcoats_vests          = models.BooleanField(default=False)
    kaftans                   = models.BooleanField(default=False)
    resortwear_sets           = models.BooleanField(default=False)
    loungewear_sleepwear      = models.BooleanField(default=False)
    activewear                = models.BooleanField(default=False)
    kidswear                  = models.BooleanField(default=False)
    accessories_scarves_stoles = models.BooleanField(default=False)

    class Meta:
        db_table = 'product_types'


class FabricCategory(models.TextChoices):
    COTTON = 'cotton', 'Cotton Based'
    SILK   = 'silk',   'Silk Based'
    LINEN  = 'linen',  'Linen & Bast'
    WOOL   = 'wool',   'Wool'
    OTHER  = 'other',  'Others'


class FabricAnswer(FlagMixin):
    """
    B.2 — One row per fabric (seeded from the 40+ fabric list in the form).
    works_with + is_primary are the core recommendation signals.
    innovation_note is free text for ML feature extraction later.
    """
    seller_profile  = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='fabric_answers')
    category        = models.CharField(max_length=20, choices=FabricCategory.choices)
    fabric_name     = models.CharField(max_length=150)
    works_with      = models.BooleanField(default=False)
    innovation_note = models.TextField(null=True, blank=True)
    is_primary      = models.BooleanField(null=True, blank=True)  # True=Primary, False=Secondary, None=N/A

    class Meta:
        db_table        = 'fabric_answers'
        unique_together = [['seller_profile', 'fabric_name']]
        indexes         = [models.Index(fields=['seller_profile', 'works_with', 'is_primary'])]


def brand_image_upload_path(instance, filename):
    return f'sellers/{instance.seller_profile_id}/brands/{filename}'


class BrandExperience(FlagMixin):
    """B.3 — Brands/buyers worked for. Direct image upload instead of Drive link."""
    seller_profile = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='brand_experiences')
    brand_name     = models.CharField(max_length=300)
    scope          = models.TextField(null=True, blank=True)
    image          = models.FileField(upload_to=brand_image_upload_path, null=True, blank=True)
    file_name      = models.CharField(max_length=255, null=True, blank=True)
    mime_type      = models.CharField(max_length=100, null=True, blank=True)
    file_size_kb   = models.IntegerField(null=True, blank=True)
    order          = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'brand_experiences'
        ordering = ['order']


class AwardMention(FlagMixin):
    """B.4 — Awards and press mentions."""
    seller_profile = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='awards')
    award_name     = models.CharField(max_length=300)
    link           = models.URLField(null=True, blank=True)
    order          = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'award_mentions'
        ordering = ['order']


# ─────────────────────────────────────────────────────────────────────────────
# SECTION C — Crafts & Production
# ─────────────────────────────────────────────────────────────────────────────
class InnovationLevel(models.TextChoices):
    HIGH   = 'high',   'High'
    MEDIUM = 'medium', 'Medium'
    LOW    = 'low',    'Low'


class DelayLikelihood(models.TextChoices):
    HIGH   = 'high',   'High'
    MEDIUM = 'medium', 'Medium'
    LOW    = 'low',    'Low'


def craft_image_upload_path(instance, filename):
    return f'sellers/{instance.seller_profile_id}/crafts/{filename}'


class CraftDetail(FlagMixin):
    """
    C.1 — One row per craft. The richest recommendation signal in the system.
    sampling_time_weeks + production_timeline_months_50units are used to
    match buyer timelines. innovation_level + delay_likelihood are used
    for risk scoring in recommendations.
    """
    seller_profile                      = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='crafts')
    craft_name                          = models.CharField(max_length=200)
    specialization                      = models.TextField(null=True, blank=True)
    is_primary                          = models.BooleanField(default=True)
    innovation_level                    = models.CharField(max_length=10, choices=InnovationLevel.choices, null=True, blank=True)
    limitations                         = models.TextField(null=True, blank=True)
    sampling_time_weeks                 = models.FloatField(null=True, blank=True)
    production_timeline_months_50units  = models.FloatField(null=True, blank=True)
    delay_likelihood                    = models.CharField(max_length=10, choices=DelayLikelihood.choices, null=True, blank=True)
    delay_common_reasons                = models.TextField(null=True, blank=True)
    image                               = models.FileField(upload_to=craft_image_upload_path, null=True, blank=True)
    file_name                           = models.CharField(max_length=255, null=True, blank=True)
    mime_type                           = models.CharField(max_length=100, null=True, blank=True)
    file_size_kb                        = models.IntegerField(null=True, blank=True)
    order                               = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'craft_details'
        ordering = ['-is_primary', 'order']
        indexes  = [
            models.Index(fields=['seller_profile', 'is_primary']),
            models.Index(fields=['craft_name']),
        ]

    def __str__(self):
        tag = 'Primary' if self.is_primary else 'Secondary'
        return f'{self.craft_name} ({tag})'


# ─────────────────────────────────────────────────────────────────────────────
# SECTION D — Collaboration & Design Support
# ─────────────────────────────────────────────────────────────────────────────
class CollabDesign(FlagMixin):
    """
    D.1 Has designer on-board?  D.2 Can develop from references?
    D.3 Max sampling iterations  D.4 → BuyerRequirement (child, up to 5 rows)
    """
    seller_profile                  = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='collab_design')
    has_fashion_designer            = models.BooleanField(null=True, blank=True)
    can_develop_from_references     = models.BooleanField(null=True, blank=True)
    max_sampling_iterations         = models.IntegerField(null=True, blank=True)

    # Per-field flags
    designer_flagged                = models.BooleanField(default=False)
    designer_flag_reason            = models.TextField(null=True, blank=True)
    references_flagged              = models.BooleanField(default=False)
    references_flag_reason          = models.TextField(null=True, blank=True)
    iterations_flagged              = models.BooleanField(default=False)
    iterations_flag_reason          = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'collab_design'


class BuyerRequirement(FlagMixin):
    """D.4 — Up to 5 pre-call questions the seller wants to ask buyers."""
    collab   = models.ForeignKey(CollabDesign, on_delete=models.CASCADE, related_name='buyer_requirements')
    order    = models.PositiveIntegerField()  # 1–5
    question = models.TextField()

    class Meta:
        db_table        = 'buyer_requirements'
        ordering        = ['order']
        unique_together = [['collab', 'order']]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION E — Batch Size & Production Scale
# ─────────────────────────────────────────────────────────────────────────────
class ProductionScale(FlagMixin):
    """
    E.1 Monthly capacity  E.2 Strict minimums?  E.3 → MOQEntry (child rows)
    monthly_capacity_units is a primary filter in recommendation queries.
    """
    seller_profile          = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='production_scale')
    monthly_capacity_units  = models.IntegerField(null=True, blank=True)
    has_strict_minimums     = models.BooleanField(null=True, blank=True)

    # Per-field flags
    capacity_flagged        = models.BooleanField(default=False)
    capacity_flag_reason    = models.TextField(null=True, blank=True)
    minimums_flagged        = models.BooleanField(default=False)
    minimums_flag_reason    = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'production_scale'
        indexes  = [models.Index(fields=['monthly_capacity_units'])]


class MOQEntry(FlagMixin):
    """E.3 — MOQ condition per craft/category (repeating rows)."""
    production_scale    = models.ForeignKey(ProductionScale, on_delete=models.CASCADE, related_name='moq_entries')
    craft_or_category   = models.CharField(max_length=200)
    moq_condition       = models.TextField()
    order               = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'moq_entries'
        ordering = ['order']


# ─────────────────────────────────────────────────────────────────────────────
# SECTION F — Process Readiness
# ─────────────────────────────────────────────────────────────────────────────
class ProcessReadiness(FlagMixin):
    """
    F.1 — Full production steps (design → delivery).
    F.2 → BTSMedia (child, direct file upload).
    """
    seller_profile    = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='process_readiness')
    production_steps  = models.TextField(null=True, blank=True)

    # Per-field flags
    steps_flagged     = models.BooleanField(default=False)
    steps_flag_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'process_readiness'


def bts_upload_path(instance, filename):
    return f'sellers/{instance.process_readiness.seller_profile_id}/bts/{filename}'


class BTSMedia(FlagMixin):
    """F.2 — Behind-the-scenes + promotional content. Direct upload, no Drive."""
    process_readiness = models.ForeignKey(ProcessReadiness, on_delete=models.CASCADE, related_name='bts_media')
    file              = models.FileField(upload_to=bts_upload_path)
    file_name         = models.CharField(max_length=255)
    mime_type         = models.CharField(max_length=100)
    file_size_kb      = models.IntegerField()
    caption           = models.CharField(max_length=300, null=True, blank=True)
    order             = models.PositiveIntegerField(default=1)
    uploaded_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bts_media'
        ordering = ['order']