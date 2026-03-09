# core/serializers.py
from rest_framework import serializers
from .models import User, UserRole, AdminProfile, SellerAccount, SellerProfile, CustomerProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'email', 'role', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class CustomerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model  = CustomerProfile
        fields = [
            'id', 'email', 'full_name', 'phone', 'date_of_birth',
            'avatar_url', 'address_line1', 'address_line2',
            'city', 'state', 'country', 'postal_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'email', 'created_at', 'updated_at']


class CustomerRegistrationSerializer(serializers.Serializer):
    email          = serializers.EmailField()
    supertokens_id = serializers.CharField()
    full_name      = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def create(self, validated_data):
        user = User.objects.create(
            email          = validated_data['email'],
            supertokens_id = validated_data['supertokens_id'],
            role           = UserRole.CUSTOMER,
        )
        CustomerProfile.objects.create(
            user      = user,
            full_name = validated_data.get('full_name', ''),
        )
        return user


class SellerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SellerProfile
        fields = ['id', 'profile_name', 'avatar_url', 'bio', 'is_active', 'is_default', 'created_at']
        read_only_fields = ['id', 'created_at']


class SellerAccountSerializer(serializers.ModelSerializer):
    profiles  = SellerProfileSerializer(many=True, read_only=True)
    email     = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model  = SellerAccount
        fields = [
            'id', 'email', 'business_name', 'business_email',
            'is_verified', 'is_active', 'profiles', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'profiles']


class CreateSellerSerializer(serializers.Serializer):
    email                = serializers.EmailField()
    password             = serializers.CharField(write_only=True, min_length=8)
    business_name        = serializers.CharField(max_length=300)
    business_email       = serializers.EmailField(required=False, allow_blank=True)
    initial_profile_name = serializers.CharField(max_length=150, default='Main Store')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def create(self, validated_data):
        request = self.context['request']
        user = User.objects.create_user(
            email    = validated_data['email'],
            password = validated_data['password'],
            role     = UserRole.SELLER,
        )
        seller_account = SellerAccount.objects.create(
            user           = user,
            business_name  = validated_data['business_name'],
            business_email = validated_data.get('business_email', ''),
            created_by     = request.user,
            is_verified    = True,  # admin-created sellers are pre-verified
        )
        SellerProfile.objects.create(
            seller_account = seller_account,
            profile_name   = validated_data.get('initial_profile_name', 'Main Store'),
            is_default     = True,
        )
        return seller_account


class AdminProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model  = AdminProfile
        fields = ['id', 'email', 'full_name', 'permissions_level', 'created_at']
        read_only_fields = ['id', 'created_at']