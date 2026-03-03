# core/urls.py
from django.urls import path
from .views import (
    MeView,
    CustomerProfileView,
    CustomerRegistrationHookView,
    SellerProfileListView,
    SellerProfileSwitchView,
    AdminSellerListView,
    AdminSellerDetailView,
)

urlpatterns = [
    path('me/',                            MeView.as_view(),                     name='me'),
    path('me/customer/',                   CustomerProfileView.as_view(),         name='customer-profile'),
    path('auth/customer-hook/',            CustomerRegistrationHookView.as_view(),name='customer-hook'),
    path('seller/profiles/',               SellerProfileListView.as_view(),       name='seller-profiles'),
    path('seller/profiles/switch/',        SellerProfileSwitchView.as_view(),     name='seller-switch'),
    path('admin/sellers/',                 AdminSellerListView.as_view(),         name='admin-sellers'),
    path('admin/sellers/<int:seller_id>/', AdminSellerDetailView.as_view(),       name='admin-seller-detail'),
]