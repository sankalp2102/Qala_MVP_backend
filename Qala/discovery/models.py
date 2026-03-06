# discovery/models.py
import uuid
from django.db import models
from core.models import User, SellerProfile


# ─────────────────────────────────────────────────────────────────────────────
# CHOICES
# ─────────────────────────────────────────────────────────────────────────────

class JourneyStage(models.TextChoices):
    FIGURING_IT_OUT    = 'figuring_it_out',    'Figuring It Out'
    BUILD_WITH_SUPPORT = 'build_with_support', 'Build With Support'
    READY_TO_PRODUCE   = 'ready_to_produce',   'Ready to Produce'


class BatchSize(models.TextChoices):
    UNDER_30     = 'under_30', 'Under 30 pieces'
    RANGE_30_100 = '30_100',   '30-100 pieces'
    OVER_100     = 'over_100', '100+ pieces'
    NOT_SURE     = 'not_sure', 'Not sure yet'


class CraftInterest(models.TextChoices):
    YES       = 'yes',       'Yes'
    NO        = 'no',        'No'
    EXPLORING = 'exploring', "I'm exploring"


class ExperimentationChoice(models.TextChoices):
    YES     = 'yes',     "Yes, I'd like to explore"
    NO      = 'no',      'Not a priority right now'
    SKIPPED = 'skipped', 'Skipped'


class Timeline(models.TextChoices):
    ONE_THREE = '1_3_months',    '1-3 months'
    THREE_SIX = '3_6_months',    '3-6 months'
    SIX_PLUS  = '6_plus_months', '6 months or longer'
    NOT_SURE  = 'not_sure',      'Not sure yet'
    FLEXIBLE  = 'flexible',      "I'm flexible"


class RecommendationRanking(models.TextChoices):
    HIGH   = 'high',   'High'
    MEDIUM = 'medium', 'Medium'
    LOW    = 'low',    'Low'


# ─────────────────────────────────────────────────────────────────────────────
# BUYER PROFILE
# ─────────────────────────────────────────────────────────────────────────────

class BuyerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Null until the buyer logs in / registers. Then linked permanently.
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='buyer_profiles',
    )

    # Stored in browser localStorage. Never changes. Used to resume progress.
    session_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Q9
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name  = models.CharField(max_length=150, null=True, blank=True)

    # Q1
    visual_selection_ids = models.JSONField(default=list, blank=True)

    # Q2
    product_types = models.JSONField(default=list, blank=True)

    # Q3
    fabrics            = models.JSONField(default=list, blank=True)
    fabric_is_flexible = models.BooleanField(default=False)
    fabric_not_sure    = models.BooleanField(default=False)

    # Q4
    craft_interest    = models.CharField(
        max_length=20, choices=CraftInterest.choices, null=True, blank=True
    )

    # Q4A
    crafts            = models.JSONField(default=list, blank=True)
    craft_is_flexible = models.BooleanField(default=False)
    craft_not_sure    = models.BooleanField(default=False)

    # Q4B
    experimentation = models.CharField(
        max_length=20, choices=ExperimentationChoice.choices,
        default=ExperimentationChoice.SKIPPED,
    )

    # Q5
    process_stage = models.CharField(max_length=100, null=True, blank=True)

    # Q6
    design_support = models.JSONField(default=list, blank=True)

    # Q7
    timeline = models.CharField(
        max_length=20, choices=Timeline.choices, null=True, blank=True
    )

    # Q8
    batch_size = models.CharField(
        max_length=20, choices=BatchSize.choices, null=True, blank=True
    )

    # Derived by matching engine
    journey_stage     = models.CharField(
        max_length=30, choices=JourneyStage.choices, null=True, blank=True
    )
    matching_complete = models.BooleanField(default=False)

    # Populated by relaxation engine when matching returns 0 results.
    # Each item = one minimum change that would unlock studios.
    # Example item:
    # {
    #   "change_type":   "craft_flexible",
    #   "message":       "3 studios match if you are open to being flexible on craft",
    #   "studios_count": 3,
    #   "apply_patch":   {"craft_is_flexible": true}
    # }
    zero_match_suggestions = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'buyer_profiles'
        indexes  = [
            models.Index(fields=['session_token']),
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        name = f'{self.first_name or ""} {self.last_name or ""}'.strip()
        return f'BuyerProfile: {name or str(self.id)}'

    @property
    def display_name(self):
        name = f'{self.first_name or ""} {self.last_name or ""}'.strip()
        return name or None


# ─────────────────────────────────────────────────────────────────────────────
# STUDIO RECOMMENDATION
# ─────────────────────────────────────────────────────────────────────────────

class StudioRecommendation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    buyer_profile  = models.ForeignKey(
        BuyerProfile, on_delete=models.CASCADE, related_name='recommendations'
    )
    seller_profile = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='buyer_recommendations'
    )

    rank_position = models.PositiveIntegerField()
    ranking       = models.CharField(max_length=10, choices=RecommendationRanking.choices)

    core_capability_fit = models.CharField(max_length=10, choices=RecommendationRanking.choices)
    moq_fit             = models.CharField(max_length=10, choices=RecommendationRanking.choices)
    craft_approach_fit  = models.CharField(max_length=10, choices=RecommendationRanking.choices)
    visual_affinity     = models.CharField(max_length=10, choices=RecommendationRanking.choices)

    match_reasoning      = models.JSONField(default=dict)
    what_best_at         = models.JSONField(default=list)
    what_to_keep_in_mind = models.JSONField(default=list)

    is_bonus_visual    = models.BooleanField(default=False)
    selected_image_ids = models.JSONField(default=list)
    mismatches         = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'studio_recommendations'
        unique_together = [['buyer_profile', 'seller_profile']]
        ordering        = ['rank_position']
        indexes         = [
            models.Index(fields=['buyer_profile', 'is_bonus_visual']),
            models.Index(fields=['seller_profile']),
        ]

    def __str__(self):
        return f'Rec #{self.rank_position} -> {self.seller_profile} for {self.buyer_profile}'
    
# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM INQUIRY
# ─────────────────────────────────────────────────────────────────────────────

class CustomInquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name          = models.CharField(max_length=200)
    email         = models.EmailField()
    message       = models.TextField()

    # Attach the session so admin can see their full questionnaire answers
    buyer_profile = models.ForeignKey(
        BuyerProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='custom_inquiries',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'custom_inquiries'
        ordering = ['-created_at']

    def __str__(self):
        return f'Inquiry from {self.name} <{self.email}>'
