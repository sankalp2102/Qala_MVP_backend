# discovery/matching.py
"""
Qala Discovery Engine - Matching Algorithm V1

Two phases:
  Phase 1: Hard Filters  - remove studios that clearly cannot do the job
  Phase 2: Ranking       - score remaining studios across 4 buckets (A, B, C, D)

Buckets:
  A - Core Capability Fit  (product + craft + fabric)   <- highest priority
  B - MOQ Fit
  C - Craft Approach Alignment  (experimentation appetite)
  D - Visual Affinity  (Q1 image selections)

Sorting is strictly hierarchical: A first, then B within A ties, then C, then D.

When Phase 1 returns 0 studios, the Relaxation Engine runs.
It tries relaxing one constraint at a time to find the minimum change
that would unlock studios, and returns those as zero_match_suggestions.
"""

import re
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from core.models import SellerProfile
from seller_profile.models import (
    ProductTypes, FabricAnswer, CraftDetail,
    CollabDesign, ProductionScale, StudioMedia,
)
from .models import (
    BuyerProfile, StudioRecommendation,
    RecommendationRanking, BatchSize, ExperimentationChoice,
)

logger = logging.getLogger('discovery')

HIGH   = RecommendationRanking.HIGH
MEDIUM = RecommendationRanking.MEDIUM
LOW    = RecommendationRanking.LOW

# InnovationLevel values (matching seller_profile/models.py)
INNOVATION_HIGH   = 'high'
INNOVATION_MEDIUM = 'medium'
INNOVATION_LOW    = 'low'

BATCH_SIZE_RANGES = {
    BatchSize.UNDER_30:     (0,   29),
    BatchSize.RANGE_30_100: (30,  100),
    BatchSize.OVER_100:     (101, 9999),
    BatchSize.NOT_SURE:     (30,  100),
}

# Buyer sends human-readable labels from the UI.
# We normalise them to the field names on ProductTypes model.
PRODUCT_LABEL_TO_FIELD = {
    'dresses':                        'dresses',
    'tops':                           'tops',
    'shirts':                         'shirts',
    't-shirts':                       't_shirts',
    't_shirts':                       't_shirts',
    'tunics / kurtas':                'tunics_kurtas',
    'tunics/kurtas':                  'tunics_kurtas',
    'tunics_kurtas':                  'tunics_kurtas',
    'co-ord sets':                    'coord_sets',
    'coord sets':                     'coord_sets',
    'coord_sets':                     'coord_sets',
    'jumpsuits':                      'jumpsuits',
    'skirts':                         'skirts',
    'shorts':                         'shorts',
    'trousers / pants':               'trousers_pants',
    'trousers/pants':                 'trousers_pants',
    'trousers_pants':                 'trousers_pants',
    'denim (jeans / jackets)':        'denim',
    'denim':                          'denim',
    'blazers':                        'blazers',
    'coats & jackets':                'coats_jackets',
    'coats_jackets':                  'coats_jackets',
    'capes':                          'capes',
    'waistcoats / vests':             'waistcoats_vests',
    'waistcoats_vests':               'waistcoats_vests',
    'kaftans':                        'kaftans',
    'resortwear sets':                'resortwear_sets',
    'resortwear_sets':                'resortwear_sets',
    'loungewear / sleepwear':         'loungewear_sleepwear',
    'loungewear_sleepwear':           'loungewear_sleepwear',
    'activewear':                     'activewear',
    'kidswear':                       'kidswear',
    'accessories (scarves / stoles)': 'accessories_scarves_stoles',
    'accessories_scarves_stoles':     'accessories_scarves_stoles',
}


def _normalise_product_types(raw_list: list) -> list:
    result = []
    for item in raw_list:
        key = item.lower().strip()
        field_name = PRODUCT_LABEL_TO_FIELD.get(key, key)
        if field_name not in result:
            result.append(field_name)
    return result


def _extract_moq_number(condition_text: str) -> Optional[int]:
    """Extract the lowest number from a MOQ condition string."""
    nums = [int(x) for x in re.findall(r'\d+', condition_text)]
    return min(nums) if nums else None


# ─────────────────────────────────────────────────────────────────────────────
# SCORE DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StudioScore:
    seller_profile: object

    # Bucket scores
    core_capability: str = MEDIUM
    moq_fit:         str = MEDIUM
    craft_approach:  str = MEDIUM
    visual_affinity: str = LOW

    # Sub-scores (used inside core_capability + for tie-breaking)
    product_sub: str = MEDIUM
    craft_sub:   str = MEDIUM
    fabric_sub:  str = MEDIUM

    # Content for the recommendation card
    match_reasoning:      dict = field(default_factory=dict)
    what_best_at:         list = field(default_factory=list)
    what_to_keep_in_mind: list = field(default_factory=list)
    selected_image_ids:   list = field(default_factory=list)
    mismatches:           list = field(default_factory=list)
    moq_text:             str  = ''

    # Craft reasons used for match_reasoning
    craft_reasons: list = field(default_factory=list)

    def sort_key(self):
        """Hierarchical sort A > B > C > D. High=0, Medium=1, Low=2."""
        order = {HIGH: 0, MEDIUM: 1, LOW: 2}
        return (
            order[self.core_capability],
            order[self.moq_fit],
            order[self.craft_approach],
            order[self.visual_affinity],
        )


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — HARD FILTERS
# ─────────────────────────────────────────────────────────────────────────────

def _pass_product_filter(profile: SellerProfile, buyer_products: list) -> bool:
    """
    Product type is ALWAYS a hard constraint — never softened by flexibility.
    Studio must support at least one of the buyer's selected product types.
    """
    if not buyer_products:
        return True  # buyer gave no types — skip filter

    try:
        pt = profile.product_types
    except ProductTypes.DoesNotExist:
        return False  # no data = cannot execute

    return any(
        hasattr(pt, f) and getattr(pt, f)
        for f in buyer_products
    )


def _pass_craft_filter(profile: SellerProfile, buyer: BuyerProfile) -> bool:
    """
    Case A: no crafts or not_sure -> no filter (keep all)
    Case B: specific crafts, NOT flexible -> hard filter (must match at least one)
    Case C: specific crafts + flexible -> no filter (handled in ranking)
    """
    if not buyer.crafts or buyer.craft_not_sure:
        return True  # Case A

    if buyer.craft_is_flexible:
        return True  # Case C

    # Case B — strict
    studio_crafts_lower = {
        c.lower() for c in
        profile.crafts.values_list('craft_name', flat=True)
    }
    buyer_crafts_lower = {c.lower().strip() for c in buyer.crafts}
    return bool(buyer_crafts_lower & studio_crafts_lower)


def _pass_fabric_filter(profile: SellerProfile, buyer: BuyerProfile) -> bool:
    """Same flexibility logic as craft filter."""
    if not buyer.fabrics or buyer.fabric_not_sure:
        return True  # Case A

    if buyer.fabric_is_flexible:
        return True  # Case C

    # Case B — strict
    studio_fabrics_lower = {
        f.lower() for f in
        profile.fabric_answers.filter(works_with=True).values_list('fabric_name', flat=True)
    }
    buyer_fabrics_lower = {f.lower().strip() for f in buyer.fabrics}
    return bool(buyer_fabrics_lower & studio_fabrics_lower)


def _pass_moq_filter(profile: SellerProfile, buyer: BuyerProfile) -> bool:
    """
    Only filter on extreme mismatch:
    buyer < 30 pieces AND studio has strict minimums >= 100.
    """
    if buyer.batch_size != BatchSize.UNDER_30:
        return True

    try:
        ps = profile.production_scale
        if not ps.has_strict_minimums:
            return True
        for entry in ps.moq_entries.all():
            moq = _extract_moq_number(entry.moq_condition)
            if moq and moq >= 100:
                return False
        return True
    except ProductionScale.DoesNotExist:
        return True


def _apply_filters(profiles, buyer_products: list, buyer: BuyerProfile) -> list:
    """Run all Phase 1 filters. Returns list of surviving profiles."""
    surviving = []
    for profile in profiles:
        # Must have studio details at minimum
        try:
            _ = profile.studio_details
        except Exception:
            continue

        if not _pass_product_filter(profile, buyer_products):
            logger.debug(f'Filtered: {profile} — product mismatch')
            continue
        if not _pass_craft_filter(profile, buyer):
            logger.debug(f'Filtered: {profile} — craft mismatch')
            continue
        if not _pass_fabric_filter(profile, buyer):
            logger.debug(f'Filtered: {profile} — fabric mismatch')
            continue
        if not _pass_moq_filter(profile, buyer):
            logger.debug(f'Filtered: {profile} — MOQ extreme mismatch')
            continue

        surviving.append(profile)

    return surviving


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — RANKING (BUCKETS A, B, C, D)
# ─────────────────────────────────────────────────────────────────────────────

def _score_product(profile: SellerProfile, buyer_products: list) -> str:
    """Bucket A1."""
    if not buyer_products:
        return MEDIUM
    try:
        pt = profile.product_types
    except ProductTypes.DoesNotExist:
        return LOW

    matches = sum(1 for f in buyer_products if hasattr(pt, f) and getattr(pt, f))
    ratio   = matches / len(buyer_products)

    if ratio >= 0.6:
        return HIGH
    if ratio >= 0.3:
        return MEDIUM
    return LOW


def _score_craft(profile: SellerProfile, buyer: BuyerProfile) -> tuple:
    """
    Bucket A2. Returns (score, reasons_list).
    Flexible/not_sure always returns Medium minimum.
    """
    reasons = []

    if not buyer.crafts or buyer.craft_not_sure:
        # Case A — no specific ask
        primary = list(
            profile.crafts.filter(is_primary=True)
            .values_list('craft_name', flat=True)[:3]
        )
        if primary:
            reasons.append(f"Primary crafts: {', '.join(primary)}")
        return MEDIUM, reasons

    buyer_set = {c.lower().strip() for c in buyer.crafts}
    primary_matches   = []
    secondary_matches = []

    for craft in profile.crafts.all():
        if craft.craft_name.lower() in buyer_set:
            if craft.is_primary:
                primary_matches.append(craft.craft_name)
            else:
                secondary_matches.append(craft.craft_name)

    if buyer.craft_is_flexible:
        # Case C — preference not constraint; no match still = Medium
        if primary_matches:
            reasons.append(f"Primary expertise in {', '.join(primary_matches)}")
            return HIGH, reasons
        if secondary_matches:
            reasons.append(f"Can work with {', '.join(secondary_matches)}")
            return MEDIUM, reasons
        return MEDIUM, reasons

    # Case B — strict
    if primary_matches:
        reasons.append(f"Primary expertise in {', '.join(primary_matches)}")
        return HIGH, reasons
    if secondary_matches:
        reasons.append(f"Secondary capability in {', '.join(secondary_matches)}")
        return MEDIUM, reasons
    return LOW, reasons


def _score_fabric(profile: SellerProfile, buyer: BuyerProfile) -> tuple:
    """Bucket A3. Returns (score, reasons_list)."""
    reasons = []

    if not buyer.fabrics or buyer.fabric_not_sure:
        return MEDIUM, reasons

    buyer_set = {f.lower().strip() for f in buyer.fabrics}
    primary_matches   = []
    secondary_matches = []

    for fab in profile.fabric_answers.filter(works_with=True):
        if fab.fabric_name.lower() in buyer_set:
            if fab.is_primary:
                primary_matches.append(fab.fabric_name)
            else:
                secondary_matches.append(fab.fabric_name)

    if buyer.fabric_is_flexible:
        if primary_matches:
            reasons.append(f"Works primarily with {', '.join(primary_matches[:3])}")
            return HIGH, reasons
        if secondary_matches:
            return MEDIUM, reasons
        return MEDIUM, reasons

    # Strict
    if primary_matches:
        reasons.append(f"Works primarily with {', '.join(primary_matches[:3])}")
        return HIGH, reasons
    if secondary_matches:
        return MEDIUM, reasons
    return LOW, reasons


def _score_core_capability(p_sub: str, c_sub: str, f_sub: str) -> str:
    """
    High   = 2+ sub-fits are High AND none are Low
    Medium = mix of High/Medium, no Low
    Low    = at least one constrained dimension is Low
    """
    subs = [p_sub, c_sub, f_sub]
    if LOW in subs:
        return LOW
    if subs.count(HIGH) >= 2:
        return HIGH
    return MEDIUM


def _score_moq(profile: SellerProfile, buyer: BuyerProfile) -> tuple:
    """Bucket B. Returns (score, display_text_or_empty_string)."""
    if not buyer.batch_size or buyer.batch_size == BatchSize.NOT_SURE:
        return MEDIUM, ''

    buyer_min, buyer_max = BATCH_SIZE_RANGES.get(buyer.batch_size, (30, 100))

    try:
        ps = profile.production_scale
    except ProductionScale.DoesNotExist:
        return MEDIUM, ''

    if not ps.has_strict_minimums:
        return HIGH, f"Comfortable with your batch size ({buyer_min}-{buyer_max} pieces)"

    moq_entries = list(ps.moq_entries.all())
    if not moq_entries:
        return HIGH, f"Comfortable with your batch size ({buyer_min}-{buyer_max} pieces)"

    stretch_found = False
    for entry in moq_entries:
        studio_moq = _extract_moq_number(entry.moq_condition)
        if studio_moq is None:
            continue
        if studio_moq <= buyer_max:
            return HIGH, f"Comfortable with your batch size ({buyer_min}-{buyer_max} pieces)"
        elif studio_moq <= buyer_max * 2:
            stretch_found = True
        else:
            return LOW, (
                f"MOQ is {studio_moq} units, above your preference of "
                f"{buyer_min}-{buyer_max}. They may have flexibility for the right project."
            )

    if stretch_found:
        return MEDIUM, (
            f"MOQ slightly above your preference of {buyer_min}-{buyer_max}. "
            "They may have flexibility for the right project."
        )
    return MEDIUM, ''


def _score_craft_approach(profile: SellerProfile, buyer: BuyerProfile) -> str:
    """
    Bucket C — maps buyer's experimentation appetite to studio innovation level.
    If buyer does NOT want to experiment -> any studio scores High (proven work is fine).
    If buyer DOES want to experiment -> check studio's innovation level on matched crafts.
    """
    if buyer.experimentation == ExperimentationChoice.SKIPPED:
        return MEDIUM

    if buyer.experimentation == ExperimentationChoice.NO:
        return HIGH  # any studio can deliver proven approaches

    # Buyer wants to experiment
    if not buyer.crafts:
        return MEDIUM

    buyer_set = {c.lower().strip() for c in buyer.crafts}
    matched = [
        c for c in profile.crafts.all()
        if c.craft_name.lower() in buyer_set and c.innovation_level
    ]

    if not matched:
        return MEDIUM

    levels = [c.innovation_level for c in matched]
    if INNOVATION_HIGH in levels:
        return HIGH
    if INNOVATION_MEDIUM in levels:
        return MEDIUM
    return LOW


def _score_visual_affinity(profile: SellerProfile, selected_ids: list) -> tuple:
    """
    Bucket D. Returns (score, list_of_matched_image_ids).
    High = 2+ images selected from this studio
    Medium = 1 image selected
    Low = 0
    """
    if not selected_ids:
        return LOW, []

    studio_image_ids = set(
        StudioMedia.objects.filter(
            studio__seller_profile=profile,
            media_type=StudioMedia.MediaType.WORK_DUMP,
        ).values_list('id', flat=True)
    )
    matched = [mid for mid in selected_ids if mid in studio_image_ids]

    if len(matched) >= 2:
        return HIGH, matched
    if len(matched) == 1:
        return MEDIUM, matched
    return LOW, []


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_match_reasoning(
    score: StudioScore,
    buyer: BuyerProfile,
) -> dict:
    r = {}

    # Product
    if score.product_sub == HIGH:
        labels = [t.replace('_', ' ').title() for t in buyer.product_types[:3]]
        if labels:
            r['product_match'] = f"Strong match for {', '.join(labels)}"
    elif score.product_sub == MEDIUM:
        r['product_match'] = "Partial match for your product types"

    # Craft
    if score.craft_reasons:
        r['craft_match'] = score.craft_reasons[0]

    # MOQ
    if score.moq_text:
        r['moq_alignment'] = score.moq_text
    elif score.moq_fit == HIGH:
        r['moq_alignment'] = "Comfortable with your batch size"

    # Visual affinity
    r['visual_affinity'] = (score.visual_affinity == HIGH)

    # Design support
    needs_design = (
        bool(buyer.design_support)
        and not any(
            'no' in d.lower() and 'covered' in d.lower()
            for d in buyer.design_support
        )
    )
    if needs_design:
        try:
            collab = score.seller_profile.collab_design
            if collab.has_fashion_designer or collab.can_develop_from_references:
                r['design_support_match'] = "Can help develop designs from moodboards"
        except CollabDesign.DoesNotExist:
            pass

    # Experimentation
    if (buyer.experimentation == ExperimentationChoice.YES
            and score.craft_approach == HIGH):
        r['innovation_alignment'] = "Known for experimentation with crafts"

    return r


def _build_what_best_at(profile: SellerProfile) -> list:
    try:
        return list(
            profile.studio_details.usps
            .order_by('order')
            .values_list('strength', flat=True)[:4]
        )
    except Exception:
        return []


def _build_keep_in_mind(profile: SellerProfile, buyer: BuyerProfile) -> list:
    items = []
    buyer_craft_set = {c.lower().strip() for c in (buyer.crafts or [])}

    for craft in profile.crafts.all():
        is_relevant = (
            not buyer_craft_set
            or craft.craft_name.lower() in buyer_craft_set
        )
        if not is_relevant:
            continue

        if craft.limitations:
            items.append({
                'text':     f"{craft.craft_name}: {craft.limitations}",
                'type':     'craft_limitation',
                'severity': 'info',
            })

        if craft.delay_likelihood == 'high':
            text = "High likelihood of delays"
            if craft.delay_common_reasons:
                text += f" - {craft.delay_common_reasons}"
            items.append({
                'text':     text,
                'type':     'delay',
                'severity': 'caution',
            })

    return items[:5]


def _build_mismatches(profile: SellerProfile, buyer: BuyerProfile) -> list:
    """For bonus visual cards - what specifically does NOT align."""
    mismatches = []

    if buyer.batch_size:
        buyer_min, buyer_max = BATCH_SIZE_RANGES.get(buyer.batch_size, (30, 100))
        try:
            ps = profile.production_scale
            if ps.has_strict_minimums:
                for entry in ps.moq_entries.all():
                    moq = _extract_moq_number(entry.moq_condition)
                    if moq and moq > buyer_max:
                        mismatches.append({
                            'parameter':       'moq',
                            'user_preference': f"{buyer_min}-{buyer_max} pieces",
                            'studio_value':    entry.moq_condition,
                            'explanation':     'Studio minimum order is above your preference',
                        })
                        break
        except ProductionScale.DoesNotExist:
            pass

    if buyer.fabrics and not buyer.fabric_is_flexible and not buyer.fabric_not_sure:
        buyer_set     = {f.lower() for f in buyer.fabrics}
        studio_set    = set(
            profile.fabric_answers.filter(works_with=True)
            .values_list('fabric_name', flat=True)
        )
        studio_lower  = {f.lower() for f in studio_set}
        missing       = buyer_set - studio_lower
        if missing:
            mismatches.append({
                'parameter':       'fabric',
                'user_preference': ', '.join(missing),
                'studio_value':    ', '.join(list(studio_set)[:3]),
                'explanation':     'Studio works with different fabrics than your preference',
            })

    if buyer.crafts and not buyer.craft_is_flexible and not buyer.craft_not_sure:
        buyer_craft_set  = {c.lower() for c in buyer.crafts}
        studio_craft_set = {
            c.lower() for c in
            profile.crafts.values_list('craft_name', flat=True)
        }
        missing = buyer_craft_set - studio_craft_set
        if missing:
            mismatches.append({
                'parameter':       'craft',
                'user_preference': ', '.join(missing),
                'studio_value':    ', '.join(list(studio_craft_set)[:3]),
                'explanation':     'Studio does not specialise in these craft techniques',
            })

    return mismatches


# ─────────────────────────────────────────────────────────────────────────────
# RELAXATION ENGINE
# Runs when Phase 1 returns 0 results.
# Tries relaxing one constraint at a time and counts how many studios appear.
# Returns a sorted list of suggestions, best (most studios unlocked) first.
# ─────────────────────────────────────────────────────────────────────────────

def _count_with_patch(all_profiles, buyer_products: list, buyer: BuyerProfile, patch: dict) -> int:
    """
    Create a temporary patched copy of the buyer and count how many studios survive
    Phase 1 filters with that single change applied.
    """
    patched = deepcopy(buyer)
    for key, value in patch.items():
        setattr(patched, key, value)

    patched_products = buyer_products
    if 'product_types' in patch:
        patched_products = _normalise_product_types(patch['product_types'])

    return len(_apply_filters(all_profiles, patched_products, patched))


def _run_relaxation(all_profiles, buyer_products: list, buyer: BuyerProfile) -> list:
    """
    Try each relaxation one at a time and build suggestions list.
    Only suggests changes that actually unlock at least 1 studio.
    Sorted by studios_count descending (best suggestion first).
    """
    candidates = []

    # 1. Make craft flexible (if buyer chose strict crafts)
    if buyer.crafts and not buyer.craft_is_flexible and not buyer.craft_not_sure:
        patch = {'craft_is_flexible': True}
        count = _count_with_patch(all_profiles, buyer_products, buyer, patch)
        if count > 0:
            candidates.append({
                'change_type':   'craft_flexible',
                'message':       (
                    f"{count} studio{'s' if count > 1 else ''} match if you are open to "
                    "being flexible on craft technique"
                ),
                'studios_count': count,
                'apply_patch':   patch,
            })

    # 2. Make fabric flexible (if buyer chose strict fabrics)
    if buyer.fabrics and not buyer.fabric_is_flexible and not buyer.fabric_not_sure:
        patch = {'fabric_is_flexible': True}
        count = _count_with_patch(all_profiles, buyer_products, buyer, patch)
        if count > 0:
            candidates.append({
                'change_type':   'fabric_flexible',
                'message':       (
                    f"{count} studio{'s' if count > 1 else ''} match if you are open to "
                    "being flexible on fabric preference"
                ),
                'studios_count': count,
                'apply_patch':   patch,
            })

    # 3. Increase batch size by one tier (if buyer chose under_30)
    if buyer.batch_size == BatchSize.UNDER_30:
        patch = {'batch_size': BatchSize.RANGE_30_100}
        count = _count_with_patch(all_profiles, buyer_products, buyer, patch)
        if count > 0:
            candidates.append({
                'change_type':   'batch_size_up',
                'message':       (
                    f"{count} studio{'s' if count > 1 else ''} match if you consider "
                    "30-100 pieces instead of under 30"
                ),
                'studios_count': count,
                'apply_patch':   patch,
            })

    # 4. Both craft and fabric flexible at once (if both were strict)
    if (buyer.crafts and not buyer.craft_is_flexible and not buyer.craft_not_sure
            and buyer.fabrics and not buyer.fabric_is_flexible and not buyer.fabric_not_sure):
        patch = {'craft_is_flexible': True, 'fabric_is_flexible': True}
        count = _count_with_patch(all_profiles, buyer_products, buyer, patch)
        if count > 0:
            candidates.append({
                'change_type':   'craft_and_fabric_flexible',
                'message':       (
                    f"{count} studio{'s' if count > 1 else ''} match if you are flexible "
                    "on both craft technique and fabric"
                ),
                'studios_count': count,
                'apply_patch':   patch,
            })

    # 5. Clear crafts entirely (fallback — try with no craft constraint)
    if buyer.crafts:
        patch = {'crafts': [], 'craft_is_flexible': False, 'craft_not_sure': True}
        count = _count_with_patch(all_profiles, buyer_products, buyer, patch)
        if count > 0:
            candidates.append({
                'change_type':   'craft_open',
                'message':       (
                    f"{count} studio{'s' if count > 1 else ''} match if you explore "
                    "all craft techniques available"
                ),
                'studios_count': count,
                'apply_patch':   patch,
            })

    # Sort by studios_count descending — best suggestion first
    candidates.sort(key=lambda x: x['studios_count'], reverse=True)

    # Only return top 3 most impactful suggestions
    return candidates[:3]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def _get_all_profiles():
    """Fetch all active verified seller profiles with required related data."""
    return SellerProfile.objects.filter(
        is_active=True,
        seller_account__is_verified=True,
    ).select_related(
        'seller_account',
        'studio_details',
        'product_types',
        'collab_design',
        'production_scale',
    ).prefetch_related(
        'crafts',
        'fabric_answers',
        'studio_details__usps',
        'studio_details__media_files',
        'production_scale__moq_entries',
    )


def run_matching(buyer: BuyerProfile) -> list:
    """
    Run the full two-phase matching algorithm for a buyer profile.
    Clears previous results, saves new ones, returns saved StudioRecommendation objects.

    If 0 studios pass Phase 1, runs the relaxation engine and saves
    zero_match_suggestions on the buyer profile instead of recommendations.
    """
    logger.info(f'Running matching for buyer {buyer.id}')

    # Clear previous results
    StudioRecommendation.objects.filter(buyer_profile=buyer).delete()

    buyer_products = _normalise_product_types(buyer.product_types or [])
    all_profiles   = list(_get_all_profiles())

    # ── PHASE 1 ───────────────────────────────────────────────────────────────
    surviving = _apply_filters(all_profiles, buyer_products, buyer)
    logger.info(f'{len(surviving)} studios passed Phase 1 for buyer {buyer.id}')

    # ── ZERO MATCH — run relaxation engine ───────────────────────────────────
    if not surviving:
        suggestions = _run_relaxation(all_profiles, buyer_products, buyer)
        buyer.zero_match_suggestions = suggestions
        buyer.matching_complete      = True
        buyer.save(update_fields=['zero_match_suggestions', 'matching_complete'])
        logger.info(
            f'Zero match for buyer {buyer.id}. '
            f'Generated {len(suggestions)} suggestions.'
        )
        return []

    # ── PHASE 2 — RANKING ─────────────────────────────────────────────────────
    scored = []
    for profile in surviving:
        s = StudioScore(seller_profile=profile)

        # Bucket A
        s.product_sub                = _score_product(profile, buyer_products)
        s.craft_sub, s.craft_reasons = _score_craft(profile, buyer)
        s.fabric_sub, _              = _score_fabric(profile, buyer)
        s.core_capability            = _score_core_capability(s.product_sub, s.craft_sub, s.fabric_sub)

        # Bucket B
        s.moq_fit, s.moq_text = _score_moq(profile, buyer)

        # Bucket C
        s.craft_approach = _score_craft_approach(profile, buyer)

        # Bucket D
        s.visual_affinity, s.selected_image_ids = _score_visual_affinity(
            profile, buyer.visual_selection_ids or []
        )

        # Build card content
        s.match_reasoning      = _build_match_reasoning(s, buyer)
        s.what_best_at         = _build_what_best_at(profile)
        s.what_to_keep_in_mind = _build_keep_in_mind(profile, buyer)

        scored.append(s)

    scored.sort(key=lambda s: s.sort_key())

    # ── SELECT TOP 3-5 ────────────────────────────────────────────────────────
    top_5          = scored[:5]
    top_5_ids      = {s.seller_profile.id for s in top_5}

    # Bonus visual: studios with HIGH visual affinity NOT in top 5
    # Check both the ranked-but-not-top-5 and the Phase 1 filtered-out studios
    bonus_candidates = []

    # From ranked studios outside top 5
    for s in scored[5:]:
        if s.visual_affinity == HIGH:
            s.mismatches = _build_mismatches(s.seller_profile, buyer)
            bonus_candidates.append(s)

    # From all profiles (including filtered-out ones)
    seen_for_bonus = set(top_5_ids) | {s.seller_profile.id for s in bonus_candidates}
    for profile in all_profiles:
        if profile.id in seen_for_bonus:
            continue
        va, matched_ids = _score_visual_affinity(profile, buyer.visual_selection_ids or [])
        if va == HIGH:
            bonus = StudioScore(
                seller_profile     = profile,
                visual_affinity    = HIGH,
                selected_image_ids = matched_ids,
                mismatches         = _build_mismatches(profile, buyer),
                what_best_at       = _build_what_best_at(profile),
            )
            bonus_candidates.append(bonus)
            seen_for_bonus.add(profile.id)

    # Cap at 2 bonus cards
    bonus_final = bonus_candidates[:2]

    # ── SAVE RESULTS ──────────────────────────────────────────────────────────
    saved = []

    for rank, s in enumerate(top_5, start=1):
        rec = StudioRecommendation.objects.create(
            buyer_profile        = buyer,
            seller_profile       = s.seller_profile,
            rank_position        = rank,
            ranking              = s.core_capability,
            core_capability_fit  = s.core_capability,
            moq_fit              = s.moq_fit,
            craft_approach_fit   = s.craft_approach,
            visual_affinity      = s.visual_affinity,
            match_reasoning      = s.match_reasoning,
            what_best_at         = s.what_best_at,
            what_to_keep_in_mind = s.what_to_keep_in_mind,
            selected_image_ids   = s.selected_image_ids,
            is_bonus_visual      = False,
        )
        saved.append(rec)

    for bonus in bonus_final:
        rec = StudioRecommendation.objects.create(
            buyer_profile        = buyer,
            seller_profile       = bonus.seller_profile,
            rank_position        = 99,
            ranking              = MEDIUM,
            core_capability_fit  = MEDIUM,
            moq_fit              = MEDIUM,
            craft_approach_fit   = MEDIUM,
            visual_affinity      = HIGH,
            match_reasoning      = {},
            what_best_at         = bonus.what_best_at,
            what_to_keep_in_mind = [],
            selected_image_ids   = bonus.selected_image_ids,
            mismatches           = bonus.mismatches,
            is_bonus_visual      = True,
        )
        saved.append(rec)

    # Clear suggestions (match was successful)
    buyer.zero_match_suggestions = []
    buyer.matching_complete      = True
    buyer.save(update_fields=['zero_match_suggestions', 'matching_complete'])

    logger.info(
        f'Matching done for buyer {buyer.id}: '
        f'{len(top_5)} recommendations, {len(bonus_final)} bonus visual matches'
    )

    return saved