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
    """
    Short summary for the context strip on the recommendations page.
    e.g. "Dresses, Tops • Hand block printing • 30-100 pieces"
    """
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
    """Build the standard recommendations response dict."""
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


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/discovery/images/
# Returns all work_dump images for Q1 visual selection grid
# Public — no auth required
# ─────────────────────────────────────────────────────────────────────────────

class VisualGridImagesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        images = StudioMedia.objects.filter(
            media_type=StudioMedia.MediaType.WORK_DUMP,
            studio__seller_profile__is_active=True,
            studio__seller_profile__seller_account__is_verified=True,
        ).select_related('studio').order_by('?')  # randomised

        serializer = VisualGridImageSerializer(images, many=True, context={'request': request})
        return Response({
            'status': 'ok',
            'count':  images.count(),
            'images': serializer.data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/discovery/readiness-check/
# Submit questionnaire answers -> run matching -> return recommendations
# Public — no auth required
# ─────────────────────────────────────────────────────────────────────────────

class ReadinessCheckView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = ReadinessCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'status': 'error', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Resume existing session if token provided
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

        # Write all questionnaire answers onto the buyer profile
        buyer.first_name           = data.get('first_name', '')
        buyer.last_name            = data.get('last_name', '')
        buyer.visual_selection_ids = data.get('visual_selection_ids', [])
        buyer.product_types        = data.get('product_types', [])
        buyer.fabrics              = data.get('fabrics', [])
        buyer.fabric_is_flexible   = data.get('fabric_is_flexible', False)
        buyer.fabric_not_sure      = data.get('fabric_not_sure', False)
        buyer.craft_interest       = data.get('craft_interest')
        buyer.crafts               = data.get('crafts', [])
        buyer.craft_is_flexible    = data.get('craft_is_flexible', False)
        buyer.craft_not_sure       = data.get('craft_not_sure', False)
        buyer.experimentation      = data.get('experimentation', 'skipped')
        buyer.process_stage        = data.get('process_stage', '')
        buyer.design_support       = data.get('design_support', [])
        buyer.timeline             = data.get('timeline')
        buyer.batch_size           = data.get('batch_size')
        buyer.journey_stage        = _derive_journey_stage(data.get('process_stage', ''))
        buyer.matching_complete    = False
        buyer.zero_match_suggestions = []
        buyer.save()

        try:
            run_matching(buyer)
        except Exception as e:
            logger.error(f'Matching failed for buyer {buyer.id}: {e}', exc_info=True)
            return Response(
                {'status': 'error', 'message': 'Matching failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            _recommendations_response(buyer, request),
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/discovery/recommendations/?session_token=<uuid>
# Re-fetch saved recommendations (page refresh, back navigation)
# Public — no auth required
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        session_token = request.query_params.get('session_token')
        if not session_token:
            return Response(
                {'status': 'error', 'message': 'session_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response(
                {'status': 'not_found', 'message': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not buyer.matching_complete:
            return Response(
                {'status': 'pending', 'message': 'Matching not yet complete'},
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(_recommendations_response(buyer, request))


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/discovery/recommendations/edit/
# Edit answers -> re-run matching (used by context strip "Edit" button)
# Public — no auth required
# ─────────────────────────────────────────────────────────────────────────────

class EditRecommendationsView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        session_token = request.data.get('session_token')
        if not session_token:
            return Response(
                {'status': 'error', 'message': 'session_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response(
                {'status': 'not_found', 'message': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ReadinessCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'status': 'error', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        # Update only the fields that were sent — keep everything else as-is
        buyer.product_types        = data.get('product_types',        buyer.product_types)
        buyer.fabrics              = data.get('fabrics',              buyer.fabrics)
        buyer.fabric_is_flexible   = data.get('fabric_is_flexible',   buyer.fabric_is_flexible)
        buyer.fabric_not_sure      = data.get('fabric_not_sure',      buyer.fabric_not_sure)
        buyer.craft_interest       = data.get('craft_interest',       buyer.craft_interest)
        buyer.crafts               = data.get('crafts',               buyer.crafts)
        buyer.craft_is_flexible    = data.get('craft_is_flexible',    buyer.craft_is_flexible)
        buyer.craft_not_sure       = data.get('craft_not_sure',       buyer.craft_not_sure)
        buyer.experimentation      = data.get('experimentation',      buyer.experimentation)
        buyer.process_stage        = data.get('process_stage',        buyer.process_stage)
        buyer.design_support       = data.get('design_support',       buyer.design_support)
        buyer.timeline             = data.get('timeline',             buyer.timeline)
        buyer.batch_size           = data.get('batch_size',           buyer.batch_size)
        buyer.journey_stage        = _derive_journey_stage(
            data.get('process_stage', buyer.process_stage or '')
        )
        buyer.matching_complete      = False
        buyer.zero_match_suggestions = []
        buyer.save()

        try:
            run_matching(buyer)
        except Exception as e:
            logger.error(f'Re-matching failed for buyer {buyer.id}: {e}', exc_info=True)
            return Response(
                {'status': 'error', 'message': 'Matching failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(_recommendations_response(buyer, request))


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/discovery/session/?session_token=<uuid>
# Returns saved questionnaire answers so frontend can restore progress on load
# Public — no auth required
# ─────────────────────────────────────────────────────────────────────────────

class SessionResumeView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        session_token = request.query_params.get('session_token')
        if not session_token:
            return Response(
                {'status': 'error', 'message': 'session_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response(
                {'status': 'not_found', 'message': 'No saved session found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            'status': 'ok',
            'data':   BuyerProfileSummarySerializer(buyer).data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/discovery/link-session/
# Called after buyer logs in / registers — links their anonymous BuyerProfile
# to their new User account. session_token comes from localStorage.
# Auth required — buyer must be logged in at this point.
# ─────────────────────────────────────────────────────────────────────────────

class LinkSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        session_token = request.data.get('session_token')
        if not session_token:
            return Response(
                {'status': 'error', 'message': 'session_token is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            buyer = BuyerProfile.objects.get(session_token=session_token)
        except BuyerProfile.DoesNotExist:
            return Response(
                {'status': 'not_found', 'message': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Link to this user — only if not already linked to someone else
        if buyer.user is not None and buyer.user != request.user:
            return Response(
                {'status': 'error', 'message': 'This session belongs to another account'},
                status=status.HTTP_403_FORBIDDEN,
            )

        buyer.user = request.user
        buyer.save(update_fields=['user'])

        logger.info(
            f'Linked BuyerProfile {buyer.id} to user {request.user.id}'
        )

        return Response({
            'status':          'ok',
            'buyer_profile_id': str(buyer.id),
            'session_token':    str(buyer.session_token),
            'message':         'Session linked to your account',
        })
        
class CustomInquiryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name    = (request.data.get('name')    or '').strip()
        email   = (request.data.get('email')   or '').strip()
        message = (request.data.get('message') or '').strip()
        session_token = (request.data.get('session_token') or '').strip()

        if not name or not email or not message:
            return Response(
                {'error': 'name, email and message are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try to link to existing buyer profile
        buyer_profile = None
        if session_token:
            try:
                buyer_profile = BuyerProfile.objects.get(session_token=session_token)
            except (BuyerProfile.DoesNotExist, Exception):
                pass

        CustomInquiry.objects.create(
            name=name,
            email=email,
            message=message,
            buyer_profile=buyer_profile,
        )

        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)