# discovery/views.py
import logging
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from core.models import SellerProfile
from seller_profile.models import StudioMedia
from .models import BuyerProfile, StudioRecommendation, JourneyStage, CustomInquiry
from .serializers import (
    ReadinessCheckSerializer,
    VisualGridImageSerializer,
    StudioRecommendationSerializer,
    BuyerProfileSummarySerializer,
)
from .matching import run_matching

logger = logging.getLogger('discovery')


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _derive_journey_stage(process_stage: str) -> str:
    if not process_stage:
        return JourneyStage.FIGURING_IT_OUT
    s = process_stage.lower()
    if 'sample' in s:
        return JourneyStage.READY_TO_PRODUCE
    if 'design' in s or 'sketch' in s:
        return JourneyStage.BUILD_WITH_SUPPORT
    return JourneyStage.FIGURING_IT_OUT


def _build_buyer_summary(buyer: BuyerProfile) -> dict:
    parts = []
    if buyer.product_types:
        labels = [t.replace('_', ' ').title() for t in buyer.product_types[:3]]
        if len(buyer.product_types) > 3:
            labels.append(f'+{len(buyer.product_types) - 3} more')
        parts.append(', '.join(labels))
    if buyer.crafts and not buyer.craft_not_sure:
        parts.append(', '.join(buyer.crafts[:3]))
    if buyer.batch_size and buyer.batch_size != 'not_sure':
        label = {
            'under_30': 'Under 30 pieces',
            '30_100':   '30-100 pieces',
            'over_100': '100+ pieces',
        }.get(buyer.batch_size, '')
        if label:
            parts.append(label)
    return {
        'display':       ' • '.join(parts),
        'product_types': buyer.product_types,
        'crafts':        buyer.crafts,
        'fabrics':       buyer.fabrics,
        'batch_size':    buyer.batch_size,
        'timeline':      buyer.timeline,
    }


def _recommendations_response(buyer: BuyerProfile, request) -> dict:
    context = {'request': request}
    recs = StudioRecommendation.objects.filter(
        buyer_profile=buyer, is_bonus_visual=False
    ).select_related('seller_profile').order_by('rank_position')
    bonus = StudioRecommendation.objects.filter(
        buyer_profile=buyer, is_bonus_visual=True
    ).select_related('seller_profile')
    total = SellerProfile.objects.filter(
        is_active=True, seller_account__is_verified=True
    ).count()
    return {
        'status':                  'ok',
        'buyer_profile_id':        str(buyer.id),
        'session_token':           str(buyer.session_token),
        'journey_stage':           buyer.journey_stage,
        'matching_complete':       buyer.matching_complete,
        'zero_match':              (buyer.matching_complete and not recs.exists()),
        'zero_match_suggestions':  buyer.zero_match_suggestions,
        'recommendations':         StudioRecommendationSerializer(recs, many=True, context=context).data,
        'bonus_visual_matches':    StudioRecommendationSerializer(bonus, many=True, context=context).data,
        'total_studios_available': total,
        'buyer_summary':           _build_buyer_summary(buyer),
    }


def _studio_inquiry_data(inq) -> dict:
    """Shared serialiser for StudioInquiry — used by both admin and seller views."""
    b = inq.buyer_profile
    return {
        'id':         str(inq.id),
        'name':       inq.name,
        'email':      inq.email,
        'answers':    inq.answers,
        'created_at': inq.created_at.isoformat(),
        'buyer': {
            'id':            str(b.id),
            'journey_stage': b.journey_stage,
            'product_types': b.product_types or [],
            'crafts':        b.crafts or [],
            'batch_size':    b.batch_size,
            'timeline':      b.timeline,
        } if b else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/discovery/images/
# ─────────────────────────────────────────────────────────────────────────────

class VisualGridImagesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        images = StudioMedia.objects.filter(
            media_type=StudioMedia.MediaType.WORK_DUMP,
            studio__seller_profile__is_active=True,
            studio__seller_profile__seller_account__is_verified=True,
        ).select_related('studio').order_by('?')
        serializer = VisualGridImageSerializer(images, many=True, context={'request': request})
        return Response({'status': 'ok', 'count': images.count(), 'images': serializer.data})


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/discovery/readiness-check/
# ─────────────────────────────────────────────────────────────────────────────

class ReadinessCheckView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = ReadinessCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data          = serializer.validated_data
        buyer         = None
        session_token = data.get('session_token')

        if session_token:
            try:
                buyer = BuyerProfile.objects.get(session_token=session_token)
                logger.info(f'Resuming session {session_token}')
            except BuyerProfile.DoesNotExist:
                logger.warning(f'Session token {session_token} not found - creating new')

        if buyer is None:
            buyer = BuyerProfile()

        buyer.first_name             = data.get('first_name', '')
        buyer.last_name              = data.get('last_name', '')
        buyer.visual_selection_ids   = data.get('visual_selection_ids', [])
        buyer.product_types          = data.get('product_types', [])
        buyer.fabrics                = data.get('fabrics', [])
        buyer.fabric_is_flexible     = data.get('fabric_is_flexible', False)
        buyer.fabric_not_sure        = data.get('fabric_not_sure', False)
        buyer.craft_interest         = data.get('craft_interest')
        buyer.crafts                 = data.get('crafts', [])
        buyer.craft_is_flexible      = data.get('craft_is_flexible', False)
        buyer.craft_not_sure         = data.get('craft_not_sure', False)
        buyer.experimentation        = data.get('experimentation', 'skipped')
        buyer.process_stage          = data.get('process_stage', '')
        buyer.design_support         = data.get('design_support', [])
        buyer.timeline               = data.get('timeline')
        buyer.batch_size             = data.get('batch_size')
        buyer.journey_stage          = _derive_journey_stage(data.get('process_stage', ''))
        buyer.matching_complete      = False
        buyer.zero_match_suggestions = []
        buyer.save()

        try:
            run_matching(buyer)
        except Exception as e:
            logger.error(f'Matching failed for buyer {buyer.id}: {e}', exc_info=True)
            return Response({'status': 'error', 'message': 'Matching failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(_recommendations_response(buyer, request), status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/discovery/recommendations/
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        session_token = request.query_params.get('session_token')
        if not session_token:
            return Response({'status': 'error', 'message': 'session_token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response({'status': 'not_found', 'message': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        if not buyer.matching_complete:
            return Response({'status': 'pending', 'message': 'Matching not yet complete'}, status=status.HTTP_202_ACCEPTED)
        return Response(_recommendations_response(buyer, request))


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/discovery/recommendations/edit/
# ─────────────────────────────────────────────────────────────────────────────

class EditRecommendationsView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        session_token = request.data.get('session_token')
        if not session_token:
            return Response({'status': 'error', 'message': 'session_token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response({'status': 'not_found', 'message': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        apply_patch = request.data.get('apply_suggestion')
        if apply_patch:
            for field, value in apply_patch.items():
                if hasattr(buyer, field):
                    setattr(buyer, field, value)
            buyer.matching_complete      = False
            buyer.zero_match_suggestions = []
            buyer.save()
            try:
                run_matching(buyer)
            except Exception as e:
                logger.error(f'Suggestion matching failed for buyer {buyer.id}: {e}', exc_info=True)
                return Response({'status': 'error', 'message': 'Matching failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response(_recommendations_response(buyer, request))

        serializer = ReadinessCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        buyer.product_types          = data.get('product_types',      buyer.product_types)
        buyer.fabrics                = data.get('fabrics',            buyer.fabrics)
        buyer.fabric_is_flexible     = data.get('fabric_is_flexible', buyer.fabric_is_flexible)
        buyer.fabric_not_sure        = data.get('fabric_not_sure',    buyer.fabric_not_sure)
        buyer.craft_interest         = data.get('craft_interest',     buyer.craft_interest)
        buyer.crafts                 = data.get('crafts',             buyer.crafts)
        buyer.craft_is_flexible      = data.get('craft_is_flexible',  buyer.craft_is_flexible)
        buyer.craft_not_sure         = data.get('craft_not_sure',     buyer.craft_not_sure)
        buyer.experimentation        = data.get('experimentation',    buyer.experimentation)
        buyer.process_stage          = data.get('process_stage',      buyer.process_stage)
        buyer.design_support         = data.get('design_support',     buyer.design_support)
        buyer.timeline               = data.get('timeline',           buyer.timeline)
        buyer.batch_size             = data.get('batch_size',         buyer.batch_size)
        buyer.journey_stage          = _derive_journey_stage(data.get('process_stage', buyer.process_stage or ''))
        buyer.matching_complete      = False
        buyer.zero_match_suggestions = []
        buyer.save()

        try:
            run_matching(buyer)
        except Exception as e:
            logger.error(f'Re-matching failed for buyer {buyer.id}: {e}', exc_info=True)
            return Response({'status': 'error', 'message': 'Matching failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(_recommendations_response(buyer, request))


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/discovery/session/
# ─────────────────────────────────────────────────────────────────────────────

class SessionResumeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        session_token = request.query_params.get('session_token')
        if not session_token:
            return Response({'status': 'error', 'message': 'session_token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response({'status': 'not_found', 'message': 'No saved session found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'status': 'ok', 'data': BuyerProfileSummarySerializer(buyer).data})


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/discovery/link-session/
# ─────────────────────────────────────────────────────────────────────────────

class LinkSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        session_token = request.data.get('session_token')
        if not session_token:
            return Response({'status': 'error', 'message': 'session_token is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response({'status': 'not_found', 'message': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        if buyer.user is not None and buyer.user != request.user:
            return Response({'status': 'error', 'message': 'This session belongs to another account'}, status=status.HTTP_403_FORBIDDEN)
        buyer.user = request.user
        buyer.save(update_fields=['user'])
        logger.info(f'Linked BuyerProfile {buyer.id} to user {request.user.id}')
        return Response({'status': 'ok', 'buyer_profile_id': str(buyer.id), 'session_token': str(buyer.session_token), 'message': 'Session linked to your account'})


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM INQUIRY
# ─────────────────────────────────────────────────────────────────────────────

class CustomInquiryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name          = (request.data.get('name')          or '').strip()
        email         = (request.data.get('email')         or '').strip()
        message       = (request.data.get('message')       or '').strip()
        session_token = (request.data.get('session_token') or '').strip()

        if not name or not email or not message:
            return Response({'error': 'name, email and message are required.'}, status=status.HTTP_400_BAD_REQUEST)

        buyer_profile = None
        if session_token:
            try:
                buyer_profile = BuyerProfile.objects.get(session_token=session_token)
            except (BuyerProfile.DoesNotExist, Exception):
                pass

        CustomInquiry.objects.create(name=name, email=email, message=message, buyer_profile=buyer_profile)
        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — DISCOVERY BUYERS
# ─────────────────────────────────────────────────────────────────────────────

class AdminDiscoveryBuyerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff and getattr(request.user, 'role', None) != 'admin':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        buyers = BuyerProfile.objects.prefetch_related('recommendations').order_by('-created_at')
        data = []
        for b in buyers:
            rec_count   = b.recommendations.filter(is_bonus_visual=False).count()
            bonus_count = b.recommendations.filter(is_bonus_visual=True).count()
            data.append({
                'id':                str(b.id),
                'session_token':     str(b.session_token),
                'name':              f'{b.first_name or ""} {b.last_name or ""}'.strip() or None,
                'user_email':        b.user.email if b.user else None,
                'journey_stage':     b.journey_stage,
                'batch_size':        b.batch_size,
                'timeline':          b.timeline,
                'product_types':     b.product_types,
                'crafts':            b.crafts,
                'fabrics':           b.fabrics,
                'craft_interest':    b.craft_interest,
                'process_stage':     b.process_stage,
                'matching_complete': b.matching_complete,
                'zero_match':        b.matching_complete and rec_count == 0,
                'rec_count':         rec_count,
                'bonus_count':       bonus_count,
                'created_at':        b.created_at.isoformat(),
            })

        total        = len(data)
        zero_match   = sum(1 for d in data if d['zero_match'])
        has_match    = sum(1 for d in data if d['rec_count'] > 0)
        linked_users = sum(1 for d in data if d['user_email'])

        from collections import Counter
        all_crafts = []
        for d in data:
            all_crafts.extend(d['crafts'] or [])
        top_crafts = [{'craft': k, 'count': v} for k, v in Counter(all_crafts).most_common(8)]

        all_products = []
        for d in data:
            all_products.extend(d['product_types'] or [])
        top_products = [{'product': k, 'count': v} for k, v in Counter(all_products).most_common(8)]

        return Response({
            'status': 'ok',
            'stats': {'total': total, 'has_match': has_match, 'zero_match': zero_match, 'linked_users': linked_users},
            'top_crafts':   top_crafts,
            'top_products': top_products,
            'buyers':       data,
        })


class AdminDiscoveryBuyerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, buyer_id):
        if not request.user.is_staff and getattr(request.user, 'role', None) != 'admin':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            buyer = BuyerProfile.objects.prefetch_related('recommendations__seller_profile__studio_details').get(id=buyer_id)
        except BuyerProfile.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        recs = []
        for r in buyer.recommendations.filter(is_bonus_visual=False).order_by('rank_position'):
            try:
                sd          = r.seller_profile.studio_details
                studio_name = sd.studio_name if sd else None
                location    = ', '.join(filter(None, [sd.location_city, sd.location_state])) if sd else None
            except Exception:
                studio_name = None
                location    = None
            recs.append({
                'rank_position':        r.rank_position,
                'ranking':              r.ranking,
                'studio_id':            r.seller_profile.id,
                'studio_name':          studio_name,
                'location':             location,
                'core_capability_fit':  r.core_capability_fit,
                'moq_fit':              r.moq_fit,
                'craft_approach_fit':   r.craft_approach_fit,
                'visual_affinity':      r.visual_affinity,
                'match_reasoning':      r.match_reasoning,
                'what_best_at':         r.what_best_at,
                'what_to_keep_in_mind': r.what_to_keep_in_mind,
            })

        from .models import CustomInquiry
        inquiries = []
        for inq in CustomInquiry.objects.filter(buyer_profile=buyer).order_by('-created_at'):
            inquiries.append({'id': str(inq.id), 'name': inq.name, 'email': inq.email, 'message': inq.message, 'created_at': inq.created_at.isoformat()})

        return Response({
            'status': 'ok',
            'buyer': {
                'id':                     str(buyer.id),
                'session_token':          str(buyer.session_token),
                'name':                   f'{buyer.first_name or ""} {buyer.last_name or ""}'.strip() or None,
                'user_email':             buyer.user.email if buyer.user else None,
                'journey_stage':          buyer.journey_stage,
                'product_types':          buyer.product_types,
                'fabrics':                buyer.fabrics,
                'fabric_is_flexible':     buyer.fabric_is_flexible,
                'fabric_not_sure':        buyer.fabric_not_sure,
                'craft_interest':         buyer.craft_interest,
                'crafts':                 buyer.crafts,
                'craft_is_flexible':      buyer.craft_is_flexible,
                'craft_not_sure':         buyer.craft_not_sure,
                'experimentation':        buyer.experimentation,
                'process_stage':          buyer.process_stage,
                'design_support':         buyer.design_support,
                'timeline':               buyer.timeline,
                'batch_size':             buyer.batch_size,
                'matching_complete':      buyer.matching_complete,
                'zero_match_suggestions': buyer.zero_match_suggestions,
                'created_at':             buyer.created_at.isoformat(),
                'updated_at':             buyer.updated_at.isoformat(),
            },
            'recommendations': recs,
            'inquiries':       inquiries,
        })


class AdminDiscoveryInquiryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff and getattr(request.user, 'role', None) != 'admin':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        from .models import CustomInquiry
        inquiries = CustomInquiry.objects.select_related('buyer_profile').order_by('-created_at')
        data = []
        for inq in inquiries:
            b = inq.buyer_profile
            data.append({
                'id':         str(inq.id),
                'name':       inq.name,
                'email':      inq.email,
                'message':    inq.message,
                'created_at': inq.created_at.isoformat(),
                'buyer': {
                    'id':            str(b.id),
                    'journey_stage': b.journey_stage,
                    'product_types': b.product_types or [],
                    'crafts':        b.crafts or [],
                    'batch_size':    b.batch_size,
                    'timeline':      b.timeline,
                } if b else None,
            })
        return Response({'status': 'ok', 'count': len(data), 'inquiries': data})


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — ALL STUDIO INQUIRIES
# GET /api/admin/discovery/studio-inquiries/
# ─────────────────────────────────────────────────────────────────────────────

class AdminStudioInquiryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff and getattr(request.user, 'role', None) != 'admin':
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        from .models import StudioInquiry
        inquiries = StudioInquiry.objects.select_related(
            'seller_profile',
            'seller_profile__studio_details',
            'seller_profile__seller_account',
            'buyer_profile',
        ).order_by('-created_at')
        data = []
        for inq in inquiries:
            s = inq.seller_profile
            # Safely resolve studio name: studio_details → business_name → profile_name
            try:
                studio_name = (
                    getattr(s.studio_details, 'studio_name', None)
                    or s.seller_account.business_name
                    or s.profile_name
                )
            except Exception:
                studio_name = s.profile_name
            row = _studio_inquiry_data(inq)
            row['studio'] = {'id': s.id, 'name': studio_name}
            data.append(row)
        return Response({'status': 'ok', 'count': len(data), 'inquiries': data})


# ─────────────────────────────────────────────────────────────────────────────
# SELLER — OWN STUDIO INQUIRIES
# GET /api/seller/studio-inquiries/
# ─────────────────────────────────────────────────────────────────────────────

class SellerStudioInquiryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import StudioInquiry

        try:
            account = request.user.seller_account
        except Exception:
            return Response({'error': 'No seller account found'}, status=status.HTTP_403_FORBIDDEN)

        profile_id = request.headers.get('X-Profile-Id')
        if profile_id:
            profile = account.profiles.filter(id=profile_id, is_active=True).first()
        else:
            profile = (
                account.profiles.filter(is_default=True, is_active=True).first()
                or account.profiles.filter(is_active=True).first()
            )

        if not profile:
            return Response({'error': 'No active profile found'}, status=status.HTTP_404_NOT_FOUND)

        inquiries = StudioInquiry.objects.filter(
            seller_profile=profile
        ).select_related('buyer_profile').order_by('-created_at')

        data = [_studio_inquiry_data(inq) for inq in inquiries]
        return Response({'status': 'ok', 'count': len(data), 'inquiries': data})


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC STUDIO PROFILE
# GET /api/discovery/studios/<profile_id>/
# ─────────────────────────────────────────────────────────────────────────────

class PublicStudioProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, profile_id):
        from django.shortcuts import get_object_or_404
        from .serializers import PublicStudioProfileSerializer
        profile = get_object_or_404(SellerProfile, id=profile_id, is_active=True, seller_account__is_verified=True)
        serializer = PublicStudioProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# STUDIO INQUIRY SUBMIT
# POST /api/discovery/studios/<profile_id>/inquire/
# ─────────────────────────────────────────────────────────────────────────────

class StudioInquiryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, profile_id):
        from django.shortcuts import get_object_or_404
        from .serializers import StudioInquirySerializer
        from .models import StudioInquiry

        profile = get_object_or_404(SellerProfile, id=profile_id, is_active=True, seller_account__is_verified=True)

        serializer = StudioInquirySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data          = serializer.validated_data
        session_token = data.get('session_token')
        buyer_profile = None
        if session_token:
            try:
                buyer_profile = BuyerProfile.objects.get(session_token=session_token)
            except BuyerProfile.DoesNotExist:
                pass

        StudioInquiry.objects.create(
            seller_profile=profile,
            buyer_profile=buyer_profile,
            name=data['name'],
            email=data['email'],
            answers=data.get('answers', []),
        )
        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)
    