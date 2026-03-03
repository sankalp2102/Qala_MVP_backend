from django.shortcuts import render

# Create your views here.
# seller_profile/views.py
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from core.models import SellerProfile
from core.permissions import IsAdminUser, IsSellerUser
from .models import (
    OnboardingStatus, SectionStatus,
    StudioDetails, StudioContact, StudioUSP, StudioMedia,
    ProductTypes, FabricAnswer, BrandExperience, AwardMention,
    CraftDetail, CollabDesign, BuyerRequirement,
    ProductionScale, MOQEntry,
    ProcessReadiness, BTSMedia,
)
from .serializers import (
    OnboardingStatusSerializer, FullOnboardingSerializer,
    StudioDetailsSerializer, StudioContactSerializer, StudioUSPSerializer, StudioMediaSerializer,
    ProductTypesSerializer, FabricAnswerSerializer, FabricAnswerBulkSerializer,
    BrandExperienceSerializer, AwardMentionSerializer,
    CraftDetailSerializer,
    CollabDesignSerializer, BuyerRequirementSerializer,
    ProductionScaleSerializer, MOQEntrySerializer,
    ProcessReadinessSerializer, BTSMediaSerializer,
    AdminFlagSerializer, AdminResolveFlagSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_active_profile(request) -> SellerProfile:
    """
    Resolves the active SellerProfile from the session.
    The frontend sends X-Profile-Id header after the seller picks a profile.
    Falls back to the default profile if no header present.
    """
    profile_id = request.headers.get('X-Profile-Id')
    account    = request.user.seller_account

    if profile_id:
        return get_object_or_404(SellerProfile, id=profile_id, seller_account=account, is_active=True)

    profile = account.profiles.filter(is_default=True, is_active=True).first()
    if not profile:
        profile = account.profiles.filter(is_active=True).first()
    if not profile:
        raise SellerProfile.DoesNotExist('No active profile found.')
    return profile


def get_or_create_onboarding(profile: SellerProfile) -> OnboardingStatus:
    obj, _ = OnboardingStatus.objects.get_or_create(seller_profile=profile)
    return obj


def mark_section_in_progress(profile: SellerProfile, section: str):
    os = get_or_create_onboarding(profile)
    field = f'section_{section}_status'
    if getattr(os, field) == SectionStatus.NOT_STARTED:
        setattr(os, field, SectionStatus.IN_PROGRESS)
        os.last_saved_at = timezone.now()
        os.save(update_fields=[field, 'last_saved_at'])


def mark_section_submitted(profile: SellerProfile, section: str):
    os = get_or_create_onboarding(profile)
    field = f'section_{section}_status'
    setattr(os, field, SectionStatus.SUBMITTED)
    os.last_saved_at = timezone.now()
    os.save(update_fields=[field, 'last_saved_at'])
    os.recalculate_completion()


# ─────────────────────────────────────────────────────────────────────────────
# SELLER — Full onboarding snapshot
# GET /api/seller/onboarding/
# ─────────────────────────────────────────────────────────────────────────────
class SellerOnboardingView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        get_or_create_onboarding(profile)   # ensure status row exists
        return Response(FullOnboardingSerializer(profile).data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION A — Studio Details
# ─────────────────────────────────────────────────────────────────────────────
class StudioDetailsView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        try:
            return Response(StudioDetailsSerializer(profile.studio_details).data)
        except StudioDetails.DoesNotExist:
            return Response(None)

    def put(self, request):
        """Full save of Section A top-level fields."""
        profile  = get_active_profile(request)
        instance = StudioDetails.objects.filter(seller_profile=profile).first()
        serializer = StudioDetailsSerializer(
            instance, data=request.data,
            partial=(instance is not None)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(seller_profile=profile)
        mark_section_submitted(profile, 'a')
        return Response(serializer.data)

    def patch(self, request):
        """Partial auto-save (called on every field blur)."""
        profile  = get_active_profile(request)
        instance, _ = StudioDetails.objects.get_or_create(seller_profile=profile)
        serializer  = StudioDetailsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        mark_section_in_progress(profile, 'a')
        return Response(serializer.data)


class StudioContactView(APIView):
    permission_classes = [IsSellerUser]

    def post(self, request):
        profile = get_active_profile(request)
        studio  = get_object_or_404(StudioDetails, seller_profile=profile)
        serializer = StudioContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(studio=studio)
        return Response(serializer.data, status=201)

    def delete(self, request, contact_id):
        profile = get_active_profile(request)
        studio  = get_object_or_404(StudioDetails, seller_profile=profile)
        contact = get_object_or_404(StudioContact, id=contact_id, studio=studio)
        contact.delete()
        return Response(status=204)


class StudioUSPView(APIView):
    permission_classes = [IsSellerUser]

    def put(self, request):
        """
        Replaces all USPs for this studio.
        Body: [ { order: 1, strength: '...' }, ... ] (max 5)
        """
        profile = get_active_profile(request)
        studio  = get_object_or_404(StudioDetails, seller_profile=profile)
        items   = request.data if isinstance(request.data, list) else []

        if len(items) > 5:
            return Response({'error': 'Maximum 5 USPs allowed.'}, status=400)

        studio.usps.all().delete()
        created = []
        for item in items:
            s = StudioUSPSerializer(data=item)
            s.is_valid(raise_exception=True)
            created.append(s.save(studio=studio))

        return Response(StudioUSPSerializer(created, many=True).data)


class StudioMediaView(APIView):
    permission_classes = [IsSellerUser]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        """Upload a single image or video (hero / work_dump / bts)."""
        profile = get_active_profile(request)
        studio  = get_object_or_404(StudioDetails, seller_profile=profile)

        # Enforce hero image limit (1 only)
        media_type = request.data.get('media_type')
        if media_type == StudioMedia.MediaType.HERO:
            studio.media_files.filter(media_type=StudioMedia.MediaType.HERO).delete()

        serializer = StudioMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(studio=studio)
        return Response(serializer.data, status=201)

    def delete(self, request, media_id):
        profile = get_active_profile(request)
        studio  = get_object_or_404(StudioDetails, seller_profile=profile)
        media   = get_object_or_404(StudioMedia, id=media_id, studio=studio)
        media.file.delete(save=False)   # delete actual file from storage
        media.delete()
        return Response(status=204)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B — Product Types
# ─────────────────────────────────────────────────────────────────────────────
class ProductTypesView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        try:
            return Response(ProductTypesSerializer(profile.product_types).data)
        except ProductTypes.DoesNotExist:
            return Response(None)

    def put(self, request):
        profile   = get_active_profile(request)
        instance, _ = ProductTypes.objects.get_or_create(seller_profile=profile)
        serializer  = ProductTypesSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        mark_section_submitted(profile, 'b')
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B — Fabrics
# ─────────────────────────────────────────────────────────────────────────────
class FabricAnswerView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        return Response(FabricAnswerSerializer(profile.fabric_answers.all(), many=True).data)

    def put(self, request):
        """Bulk upsert all fabric answers at once."""
        profile    = get_active_profile(request)
        serializer = FabricAnswerBulkSerializer(data={'fabrics': request.data})
        serializer.is_valid(raise_exception=True)
        serializer.update(profile, serializer.validated_data)
        mark_section_submitted(profile, 'b')
        return Response(FabricAnswerSerializer(profile.fabric_answers.all(), many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION B — Brand Experience
# ─────────────────────────────────────────────────────────────────────────────
class BrandExperienceView(APIView):
    permission_classes = [IsSellerUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        profile = get_active_profile(request)
        return Response(BrandExperienceSerializer(profile.brand_experiences.all(), many=True).data)

    def post(self, request):
        profile    = get_active_profile(request)
        serializer = BrandExperienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(seller_profile=profile)
        return Response(serializer.data, status=201)

    def patch(self, request, brand_id):
        profile = get_active_profile(request)
        brand   = get_object_or_404(BrandExperience, id=brand_id, seller_profile=profile)
        serializer = BrandExperienceSerializer(brand, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, brand_id):
        profile = get_active_profile(request)
        brand   = get_object_or_404(BrandExperience, id=brand_id, seller_profile=profile)
        if brand.image:
            brand.image.delete(save=False)
        brand.delete()
        return Response(status=204)


class AwardMentionView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        return Response(AwardMentionSerializer(profile.awards.all(), many=True).data)

    def post(self, request):
        profile    = get_active_profile(request)
        serializer = AwardMentionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(seller_profile=profile)
        return Response(serializer.data, status=201)

    def delete(self, request, award_id):
        profile = get_active_profile(request)
        award   = get_object_or_404(AwardMention, id=award_id, seller_profile=profile)
        award.delete()
        return Response(status=204)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION C — Crafts
# ─────────────────────────────────────────────────────────────────────────────
class CraftDetailView(APIView):
    permission_classes = [IsSellerUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        profile = get_active_profile(request)
        return Response(CraftDetailSerializer(profile.crafts.all(), many=True).data)

    def post(self, request):
        profile    = get_active_profile(request)
        serializer = CraftDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(seller_profile=profile)
        mark_section_in_progress(profile, 'c')
        return Response(serializer.data, status=201)


class CraftDetailItemView(APIView):
    permission_classes = [IsSellerUser]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, craft_id):
        profile = get_active_profile(request)
        craft   = get_object_or_404(CraftDetail, id=craft_id, seller_profile=profile)
        serializer = CraftDetailSerializer(craft, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, craft_id):
        profile = get_active_profile(request)
        craft   = get_object_or_404(CraftDetail, id=craft_id, seller_profile=profile)
        if craft.image:
            craft.image.delete(save=False)
        craft.delete()
        return Response(status=204)


class CraftSectionSubmitView(APIView):
    """POST /api/seller/onboarding/crafts/submit/ — mark Section C done."""
    permission_classes = [IsSellerUser]

    def post(self, request):
        profile = get_active_profile(request)
        if not profile.crafts.exists():
            return Response({'error': 'Add at least one craft before submitting.'}, status=400)
        mark_section_submitted(profile, 'c')
        return Response({'status': 'Section C submitted.'})


# ─────────────────────────────────────────────────────────────────────────────
# SECTION D — Collab & Design
# ─────────────────────────────────────────────────────────────────────────────
class CollabDesignView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        try:
            return Response(CollabDesignSerializer(profile.collab_design).data)
        except CollabDesign.DoesNotExist:
            return Response(None)

    def put(self, request):
        profile   = get_active_profile(request)
        instance, _ = CollabDesign.objects.get_or_create(seller_profile=profile)
        serializer  = CollabDesignSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        mark_section_submitted(profile, 'd')
        return Response(serializer.data)


class BuyerRequirementView(APIView):
    permission_classes = [IsSellerUser]

    def put(self, request):
        """
        Replaces all buyer requirements (up to 5).
        Body: [ { order: 1, question: '...' }, ... ]
        """
        profile  = get_active_profile(request)
        collab   = get_object_or_404(CollabDesign, seller_profile=profile)
        items    = request.data if isinstance(request.data, list) else []

        if len(items) > 5:
            return Response({'error': 'Maximum 5 buyer requirements.'}, status=400)

        collab.buyer_requirements.all().delete()
        created = []
        for item in items:
            s = BuyerRequirementSerializer(data=item)
            s.is_valid(raise_exception=True)
            created.append(s.save(collab=collab))

        return Response(BuyerRequirementSerializer(created, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION E — Production Scale
# ─────────────────────────────────────────────────────────────────────────────
class ProductionScaleView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        try:
            return Response(ProductionScaleSerializer(profile.production_scale).data)
        except ProductionScale.DoesNotExist:
            return Response(None)

    def put(self, request):
        profile   = get_active_profile(request)
        instance, _ = ProductionScale.objects.get_or_create(seller_profile=profile)
        serializer  = ProductionScaleSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        mark_section_submitted(profile, 'e')
        return Response(serializer.data)


class MOQEntryView(APIView):
    permission_classes = [IsSellerUser]

    def put(self, request):
        """Replace all MOQ entries. Body: [ { craft_or_category, moq_condition, order } ]"""
        profile    = get_active_profile(request)
        production = get_object_or_404(ProductionScale, seller_profile=profile)
        items      = request.data if isinstance(request.data, list) else []

        production.moq_entries.all().delete()
        created = []
        for item in items:
            s = MOQEntrySerializer(data=item)
            s.is_valid(raise_exception=True)
            created.append(s.save(production_scale=production))

        return Response(MOQEntrySerializer(created, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION F — Process Readiness
# ─────────────────────────────────────────────────────────────────────────────
class ProcessReadinessView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        try:
            return Response(ProcessReadinessSerializer(profile.process_readiness).data)
        except ProcessReadiness.DoesNotExist:
            return Response(None)

    def put(self, request):
        profile   = get_active_profile(request)
        instance, _ = ProcessReadiness.objects.get_or_create(seller_profile=profile)
        serializer  = ProcessReadinessSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        mark_section_submitted(profile, 'f')
        return Response(serializer.data)


class BTSMediaView(APIView):
    permission_classes = [IsSellerUser]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        profile  = get_active_profile(request)
        process  = get_object_or_404(ProcessReadiness, seller_profile=profile)
        serializer = BTSMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(process_readiness=process)
        return Response(serializer.data, status=201)

    def delete(self, request, media_id):
        profile = get_active_profile(request)
        process = get_object_or_404(ProcessReadiness, seller_profile=profile)
        media   = get_object_or_404(BTSMedia, id=media_id, process_readiness=process)
        media.file.delete(save=False)
        media.delete()
        return Response(status=204)


# ─────────────────────────────────────────────────────────────────────────────
# SELLER — Get all flags on their own profile (dashboard notification feed)
# ─────────────────────────────────────────────────────────────────────────────
class SellerFlagSummaryView(APIView):
    """GET /api/seller/onboarding/flags/ — seller sees all unresolved admin flags."""
    permission_classes = [IsSellerUser]

    def get(self, request):
        profile = get_active_profile(request)
        flags   = []

        # Section A
        try:
            sd = profile.studio_details
            for field in ['studio_name', 'location', 'years', 'website', 'poc']:
                if getattr(sd, f'{field}_flagged', False):
                    flags.append({'section': 'A', 'model': 'studio_details',
                                  'field': field, 'reason': getattr(sd, f'{field}_flag_reason', '')})
            for contact in sd.contacts.filter(is_flagged=True, flag_resolved=False):
                flags.append({'section': 'A', 'model': 'studio_contact',
                              'object_id': contact.id, 'reason': contact.flag_reason})
            for usp in sd.usps.filter(is_flagged=True, flag_resolved=False):
                flags.append({'section': 'A', 'model': 'studio_usp',
                              'object_id': usp.id, 'reason': usp.flag_reason})
        except StudioDetails.DoesNotExist:
            pass

        # Section C — Crafts
        for craft in profile.crafts.filter(is_flagged=True, flag_resolved=False):
            flags.append({'section': 'C', 'model': 'craft',
                          'object_id': craft.id, 'craft_name': craft.craft_name,
                          'reason': craft.flag_reason})

        # Section D
        try:
            cd = profile.collab_design
            for field in ['designer', 'references', 'iterations']:
                if getattr(cd, f'{field}_flagged', False):
                    flags.append({'section': 'D', 'model': 'collab_design',
                                  'field': field, 'reason': getattr(cd, f'{field}_flag_reason', '')})
        except CollabDesign.DoesNotExist:
            pass

        # Section E
        try:
            ps = profile.production_scale
            for field in ['capacity', 'minimums']:
                if getattr(ps, f'{field}_flagged', False):
                    flags.append({'section': 'E', 'model': 'production_scale',
                                  'field': field, 'reason': getattr(ps, f'{field}_flag_reason', '')})
        except ProductionScale.DoesNotExist:
            pass

        # Section F
        try:
            pr = profile.process_readiness
            if pr.steps_flagged:
                flags.append({'section': 'F', 'model': 'process_readiness',
                              'field': 'production_steps', 'reason': pr.steps_flag_reason})
        except ProcessReadiness.DoesNotExist:
            pass

        return Response({'total_flags': len(flags), 'flags': flags})


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Flag + Resolve endpoints
# ─────────────────────────────────────────────────────────────────────────────
# Maps model name strings → (Model class, section letter)
MODEL_MAP = {
    'studio_details':   (StudioDetails,   'a', 'seller_profile_id'),
    'product_types':    (ProductTypes,    'b', 'seller_profile_id'),
    'collab_design':    (CollabDesign,    'd', 'seller_profile_id'),
    'production_scale': (ProductionScale, 'e', 'seller_profile_id'),
    'process_readiness':(ProcessReadiness,'f', 'seller_profile_id'),
    # Row-level child models (require object_id, not profile_id)
    'craft':             (CraftDetail,     'c', 'id'),
    'fabric_answer':     (FabricAnswer,    'b', 'id'),
    'brand_experience':  (BrandExperience, 'b', 'id'),
    'award_mention':     (AwardMention,    'b', 'id'),
    'studio_contact':    (StudioContact,   'a', 'id'),
    'studio_usp':        (StudioUSP,       'a', 'id'),
    'studio_media':      (StudioMedia,     'a', 'id'),
    'moq_entry':         (MOQEntry,        'e', 'id'),
    'buyer_requirement': (BuyerRequirement,'d', 'id'),
    'bts_media':         (BTSMedia,        'f', 'id'),
}

# Per-field flag pairs for models that support them
FIELD_FLAG_MAP = {
    'studio_details':   ['studio_name', 'location', 'years', 'website', 'poc'],
    'collab_design':    ['designer', 'references', 'iterations'],
    'production_scale': ['capacity', 'minimums'],
    'process_readiness':['steps'],
}


class AdminFlagView(APIView):
    """
    POST /api/admin/seller-profiles/<profile_id>/flag/
    Body: { model, object_id (optional), field (optional), reason }
    """
    permission_classes = [IsAdminUser]

    def post(self, request, profile_id):
        # Ensure profile exists and belongs to a real seller
        profile    = get_object_or_404(SellerProfile, id=profile_id)
        serializer = AdminFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        model_name = serializer.validated_data['model']
        object_id  = serializer.validated_data.get('object_id')
        field      = serializer.validated_data.get('field', '').strip()
        reason     = serializer.validated_data['reason']

        Model, section, lookup = MODEL_MAP[model_name]

        # Resolve the instance
        if lookup == 'seller_profile_id':
            instance = get_object_or_404(Model, seller_profile=profile)
        else:
            instance = get_object_or_404(Model, id=object_id)

        # Apply per-field flag if field is specified and supported
        if field and model_name in FIELD_FLAG_MAP and field in FIELD_FLAG_MAP[model_name]:
            setattr(instance, f'{field}_flagged',     True)
            setattr(instance, f'{field}_flag_reason', reason)
            instance.save(update_fields=[f'{field}_flagged', f'{field}_flag_reason'])
        else:
            # Row-level flag
            instance.apply_flag(admin_user=request.user, reason=reason)

        # Update onboarding section status
        os = get_or_create_onboarding(profile)
        os.flag_section(section)

        return Response({
            'status':      'flagged',
            'model':       model_name,
            'field':       field or 'row',
            'reason':      reason,
            'profile_id':  profile_id,
        })


class AdminResolveFlagView(APIView):
    """
    POST /api/admin/seller-profiles/<profile_id>/resolve-flag/
    Body: { model, object_id (optional), field (optional) }
    Resolves a flag and re-evaluates section status.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, profile_id):
        profile    = get_object_or_404(SellerProfile, id=profile_id)
        serializer = AdminResolveFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        model_name = serializer.validated_data['model']
        object_id  = serializer.validated_data.get('object_id')
        field      = serializer.validated_data.get('field', '').strip()

        Model, section, lookup = MODEL_MAP[model_name]

        if lookup == 'seller_profile_id':
            instance = get_object_or_404(Model, seller_profile=profile)
        else:
            instance = get_object_or_404(Model, id=object_id)

        # Resolve per-field flag
        if field and model_name in FIELD_FLAG_MAP and field in FIELD_FLAG_MAP[model_name]:
            setattr(instance, f'{field}_flagged',     False)
            setattr(instance, f'{field}_flag_reason', None)
            instance.save(update_fields=[f'{field}_flagged', f'{field}_flag_reason'])
        else:
            instance.resolve_flag()

        # If no more flags on this section → set back to SUBMITTED
        os     = get_or_create_onboarding(profile)
        field_ = f'section_{section}_status'
        if getattr(os, field_) == SectionStatus.FLAGGED:
            setattr(os, field_, SectionStatus.SUBMITTED)
            os.save(update_fields=[field_])
        os.recalculate_completion()

        return Response({'status': 'resolved', 'model': model_name, 'field': field or 'row'})


class AdminSellerOnboardingView(APIView):
    """
    GET /api/admin/seller-profiles/<profile_id>/onboarding/
    Admin reads the full onboarding snapshot for any profile.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, profile_id):
        profile = get_object_or_404(SellerProfile, id=profile_id)
        return Response(FullOnboardingSerializer(profile).data)


class AdminSellerProfileListView(APIView):
    """
    GET /api/admin/seller-profiles/
    Lists all profiles with their completion % and flag count.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        profiles = SellerProfile.objects.select_related(
            'seller_account__user', 'onboarding_status'
        ).filter(is_active=True)

        data = []
        for p in profiles:
            try:
                os = p.onboarding_status
                completion = os.completion_percentage
                section_statuses = {
                    'A': os.section_a_status, 'B': os.section_b_status,
                    'C': os.section_c_status, 'D': os.section_d_status,
                    'E': os.section_e_status, 'F': os.section_f_status,
                }
                flagged_sections = [k for k, v in section_statuses.items() if v == SectionStatus.FLAGGED]
            except OnboardingStatus.DoesNotExist:
                completion       = 0.0
                section_statuses = {}
                flagged_sections = []

            data.append({
                'profile_id':       p.id,
                'profile_name':     p.profile_name,
                'business_name':    p.seller_account.business_name,
                'seller_email':     p.seller_account.user.email,
                'completion':       completion,
                'section_statuses': section_statuses,
                'flagged_sections': flagged_sections,
                'is_verified':      p.seller_account.is_verified,
            })

        return Response(data)