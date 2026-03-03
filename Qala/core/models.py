# core/models.py
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserRole(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    SELLER   = 'seller',   'Seller'
    ADMIN    = 'admin',    'Admin'


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role=UserRole.CUSTOMER, **extra):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user  = self.model(email=email, role=role, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, role=UserRole.ADMIN, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supertokens_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    email          = models.EmailField(unique=True)
    role           = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.CUSTOMER)
    is_active      = models.BooleanField(default=True)
    is_staff       = models.BooleanField(default=False)
    date_joined    = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []
    objects         = UserManager()

    class Meta:
        db_table = 'users'
        indexes  = [
            models.Index(fields=['role']),
            models.Index(fields=['supertokens_id']),
        ]

    def __str__(self):
        return f'{self.email} ({self.role})'


class AdminProfile(models.Model):
    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    full_name         = models.CharField(max_length=200)
    permissions_level = models.IntegerField(default=1)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_profiles'

    def __str__(self):
        return f'Admin: {self.full_name}'


class SellerAccount(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_account')
    business_name  = models.CharField(max_length=300)
    business_email = models.EmailField(null=True, blank=True)
    is_verified    = models.BooleanField(default=False)
    created_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_sellers'
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'seller_accounts'

    def __str__(self):
        return f'SellerAccount: {self.business_name}'


class SellerProfile(models.Model):
    seller_account = models.ForeignKey(SellerAccount, on_delete=models.CASCADE, related_name='profiles')
    profile_name   = models.CharField(max_length=150)
    avatar_url     = models.URLField(null=True, blank=True)
    bio            = models.TextField(null=True, blank=True)
    is_active      = models.BooleanField(default=True)
    is_default     = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'seller_profiles'
        unique_together = [['seller_account', 'profile_name']]

    def __str__(self):
        return f'{self.profile_name} ({self.seller_account.business_name})'


class CustomerProfile(models.Model):
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    full_name     = models.CharField(max_length=200, null=True, blank=True)
    phone         = models.CharField(max_length=20,  null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    avatar_url    = models.URLField(null=True, blank=True)
    address_line1 = models.CharField(max_length=300, null=True, blank=True)
    address_line2 = models.CharField(max_length=300, null=True, blank=True)
    city          = models.CharField(max_length=100, null=True, blank=True)
    state         = models.CharField(max_length=100, null=True, blank=True)
    country       = models.CharField(max_length=100, default='IN')
    postal_code   = models.CharField(max_length=20,  null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_profiles'

    def __str__(self):
        return f'Customer: {self.full_name or self.user.email}'