# seller_profile/urls.py
from django.urls import path
from .views import (
    SellerOnboardingView,
    StudioDetailsView, StudioContactView, StudioUSPView, StudioMediaView,
    ProductTypesView, FabricAnswerView,
    BrandExperienceView, AwardMentionView,
    CraftDetailView, CraftDetailItemView, CraftSectionSubmitView,
    CollabDesignView, BuyerRequirementView,
    ProductionScaleView, MOQEntryView,
    ProcessReadinessView, BTSMediaView,
    SellerFlagSummaryView,
    AdminFlagView, AdminResolveFlagView,
    AdminSellerOnboardingView, AdminSellerProfileListView, AdminEditSellerSectionView,
)

urlpatterns = [
    path('seller/onboarding/',                              SellerOnboardingView.as_view(),      name='onboarding'),
    path('seller/onboarding/flags/',                        SellerFlagSummaryView.as_view(),     name='seller-flags'),

    # Section A
    path('seller/onboarding/studio/',                       StudioDetailsView.as_view(),         name='studio-details'),
    path('seller/onboarding/studio/contacts/',              StudioContactView.as_view(),         name='studio-contacts'),
    path('seller/onboarding/studio/contacts/<int:contact_id>/', StudioContactView.as_view(),     name='studio-contact-delete'),
    path('seller/onboarding/studio/usps/',                  StudioUSPView.as_view(),             name='studio-usps'),
    path('seller/onboarding/studio/media/',                 StudioMediaView.as_view(),           name='studio-media'),
    path('seller/onboarding/studio/media/<int:media_id>/',  StudioMediaView.as_view(),           name='studio-media-delete'),

    # Section B
    path('seller/onboarding/products/',                     ProductTypesView.as_view(),          name='product-types'),
    path('seller/onboarding/fabrics/',                      FabricAnswerView.as_view(),          name='fabrics'),
    path('seller/onboarding/brands/',                       BrandExperienceView.as_view(),       name='brands'),
    path('seller/onboarding/brands/<int:brand_id>/',        BrandExperienceView.as_view(),       name='brand-detail'),
    path('seller/onboarding/awards/',                       AwardMentionView.as_view(),          name='awards'),
    path('seller/onboarding/awards/<int:award_id>/',        AwardMentionView.as_view(),          name='award-delete'),

    # Section C — BUG 10 FIX: submit/ must come BEFORE crafts/ and crafts/<id>/
    path('seller/onboarding/crafts/submit/',                CraftSectionSubmitView.as_view(),    name='crafts-submit'),
    path('seller/onboarding/crafts/',                       CraftDetailView.as_view(),           name='crafts'),
    path('seller/onboarding/crafts/<int:craft_id>/',        CraftDetailItemView.as_view(),       name='craft-detail'),

    # Section D
    path('seller/onboarding/collab/',                       CollabDesignView.as_view(),          name='collab'),
    path('seller/onboarding/collab/buyer-requirements/',    BuyerRequirementView.as_view(),      name='buyer-reqs'),

    # Section E
    path('seller/onboarding/production/',                   ProductionScaleView.as_view(),       name='production'),
    path('seller/onboarding/production/moq/',               MOQEntryView.as_view(),              name='moq'),

    # Section F
    path('seller/onboarding/process/',                      ProcessReadinessView.as_view(),      name='process'),
    path('seller/onboarding/process/media/',                BTSMediaView.as_view(),              name='bts-media'),
    path('seller/onboarding/process/media/<int:media_id>/', BTSMediaView.as_view(),              name='bts-media-delete'),

    # Admin
    path('admin/seller-profiles/',                          AdminSellerProfileListView.as_view(),name='admin-profiles'),
    path('admin/seller-profiles/<int:profile_id>/onboarding/', AdminSellerOnboardingView.as_view(), name='admin-onboarding'),
    path('admin/seller-profiles/<int:profile_id>/flag/',    AdminFlagView.as_view(),             name='admin-flag'),
    path('admin/seller-profiles/<int:profile_id>/resolve-flag/', AdminResolveFlagView.as_view(), name='admin-resolve'),
    path('admin/seller-profiles/<int:profile_id>/edit/<str:section>/',
         AdminEditSellerSectionView.as_view(), name='admin-edit-section'),
    path('admin/seller-profiles/<int:profile_id>/edit/craft/<int:object_id>/',
         AdminEditSellerSectionView.as_view(), {'section': 'craft'}, name='admin-edit-craft'),
]