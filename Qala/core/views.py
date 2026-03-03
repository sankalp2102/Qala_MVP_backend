# core/views.py
import requests
import logging
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import User, UserRole, AdminProfile, SellerAccount, SellerProfile, CustomerProfile
from .serializers import (
    UserSerializer, CustomerProfileSerializer, CustomerRegistrationSerializer,
    SellerAccountSerializer, SellerProfileSerializer, CreateSellerSerializer,
    AdminProfileSerializer,
)
from .permissions import IsAdminUser, IsSellerUser, IsCustomerUser
from seller_profile.models import OnboardingStatus

logger = logging.getLogger('core')


# ── Helpers ───────────────────────────────────────────────────────────────────
def _st_headers():
    return {
        'Content-Type': 'application/json',
        'api-key': settings.SUPERTOKENS['API_KEY'],
    }


def _create_supertokens_user(email: str, password: str) -> str:
    # BUG 1 FIX: correct endpoint is /recipe/signup not /recipe/user
    url  = f"{settings.SUPERTOKENS['SUPERTOKENS_URL']}/recipe/signup"
    resp = requests.post(
        url,
        json    = {'email': email, 'password': password},
        headers = _st_headers(),
        timeout = 10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('status') not in ('OK', 'EMAIL_ALREADY_EXISTS_ERROR'):
        raise Exception(data.get('status', 'Unknown SuperTokens error'))
    return data['user']['id']


def _assign_supertokens_role(supertokens_id: str, role: str):
    # Create the role first (idempotent — safe to call even if role exists)
    requests.put(
        f"{settings.SUPERTOKENS['SUPERTOKENS_URL']}/recipe/role",
        json    = {'role': role, 'permissions': [role]},
        headers = _st_headers(),
        timeout = 10,
    )
    # Assign the role to the user
    resp = requests.put(
        f"{settings.SUPERTOKENS['SUPERTOKENS_URL']}/recipe/user/role",
        json    = {'userId': supertokens_id, 'role': role, 'tenantId': 'public'},
        headers = _st_headers(),
        timeout = 10,
    )
    resp.raise_for_status()


# ── /api/me/ ──────────────────────────────────────────────────────────────────
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        base = UserSerializer(user).data

        if user.role == UserRole.CUSTOMER:
            try:
                profile = CustomerProfileSerializer(user.customer_profile).data
            except CustomerProfile.DoesNotExist:
                profile = None
            return Response({**base, 'profile': profile})

        if user.role == UserRole.SELLER:
            try:
                account  = user.seller_account
                profiles = SellerProfileSerializer(
                    account.profiles.filter(is_active=True), many=True
                ).data
            except SellerAccount.DoesNotExist:
                account  = None
                profiles = []
            return Response({
                **base,
                'business_name': account.business_name if account else None,
                'is_verified':   account.is_verified   if account else False,
                'profiles':      profiles,
            })

        if user.role == UserRole.ADMIN:
            try:
                profile = AdminProfileSerializer(user.admin_profile).data
            except AdminProfile.DoesNotExist:
                profile = None
            return Response({**base, 'profile': profile})

        return Response(base)


# ── Customer ──────────────────────────────────────────────────────────────────
class CustomerProfileView(APIView):
    permission_classes = [IsCustomerUser]

    def get(self, request):
        profile = get_object_or_404(CustomerProfile, user=request.user)
        return Response(CustomerProfileSerializer(profile).data)

    def patch(self, request):
        profile    = get_object_or_404(CustomerProfile, user=request.user)
        serializer = CustomerProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CustomerRegistrationHookView(APIView):
    """
    Internal endpoint called by SuperTokens post-signup override.
    Protected by X-Hook-Secret header — never call this from frontend.
    """
    permission_classes = []    # no auth — validated by hook secret

    def post(self, request):
        secret = request.headers.get('X-Hook-Secret', '')
        if secret != settings.SUPERTOKENS_HOOK_SECRET:
            return Response({'error': 'Forbidden'}, status=403)

        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info(f'Customer Django record created: {user.email}')
        return Response({'id': str(user.id), 'email': user.email}, status=201)


# ── Seller — profile list + switch ───────────────────────────────────────────
class SellerProfileListView(APIView):
    permission_classes = [IsSellerUser]

    def get(self, request):
        account  = get_object_or_404(SellerAccount, user=request.user)
        profiles = account.profiles.filter(is_active=True).order_by('-is_default', 'profile_name')
        return Response(SellerProfileSerializer(profiles, many=True).data)

    def post(self, request):
        account = get_object_or_404(SellerAccount, user=request.user)
        if account.profiles.filter(is_active=True).count() >= 10:
            return Response({'error': 'Maximum 10 profiles allowed.'}, status=400)

        serializer = SellerProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(seller_account=account)
        OnboardingStatus.objects.get_or_create(seller_profile=profile)
        return Response(serializer.data, status=201)


class SellerProfileSwitchView(APIView):
    permission_classes = [IsSellerUser]

    def post(self, request):
        profile_id = request.data.get('profile_id')
        if not profile_id:
            return Response({'error': 'profile_id is required.'}, status=400)

        account = get_object_or_404(SellerAccount, user=request.user)
        profile = get_object_or_404(
            SellerProfile,
            id             = profile_id,
            seller_account = account,
            is_active      = True,
        )
        return Response({
            'active_profile': SellerProfileSerializer(profile).data,
            'message': f'Switched to "{profile.profile_name}".',
        })


# ── Admin — seller management ─────────────────────────────────────────────────
class AdminSellerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        accounts = SellerAccount.objects.select_related('user').prefetch_related('profiles').all()
        return Response(SellerAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = CreateSellerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        seller_account = serializer.save()
        user           = seller_account.user

        try:
            st_user_id = _create_supertokens_user(
                email    = user.email,
                password = request.data.get('password'),
            )
            user.supertokens_id = st_user_id
            user.save(update_fields=['supertokens_id'])
            _assign_supertokens_role(st_user_id, 'seller')
        except Exception as e:
            user.delete()
            logger.error(f'SuperTokens seller creation failed: {e}')
            return Response(
                {'error': f'SuperTokens registration failed: {str(e)}'},
                status=502,
            )

        default_profile = seller_account.profiles.filter(is_default=True).first()
        if default_profile:
            OnboardingStatus.objects.get_or_create(seller_profile=default_profile)

        return Response(SellerAccountSerializer(seller_account).data, status=201)


class AdminSellerDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, seller_id):
        account = get_object_or_404(SellerAccount, id=seller_id)
        return Response(SellerAccountSerializer(account).data)

    def patch(self, request, seller_id):
        account    = get_object_or_404(SellerAccount, id=seller_id)
        serializer = SellerAccountSerializer(account, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, seller_id):
        account            = get_object_or_404(SellerAccount, id=seller_id)
        account.user.is_active = False
        account.user.save(update_fields=['is_active'])
        return Response({'message': 'Seller deactivated.'})