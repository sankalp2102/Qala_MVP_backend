# discovery/urls.py
from django.urls import path
from .views import (
    VisualGridImagesView,
    ReadinessCheckView,
    RecommendationsView,
    EditRecommendationsView,
    SessionResumeView,
    LinkSessionView,
    CustomInquiryView,
    PublicStudioProfileView,
    StudioInquiryView,
    AdminDiscoveryBuyerListView,
    AdminDiscoveryBuyerDetailView,
    AdminDiscoveryInquiryListView,
    AdminStudioInquiryListView,
    SellerStudioInquiryView,
    StudioDirectoryView,
)

urlpatterns = [
    # Q1 — visual image grid (all work_dump images from active studios)
    path('discovery/images/',               VisualGridImagesView.as_view()),

    # Submit all 8 answers -> run matching -> returns recommendations
    path('discovery/readiness-check/',      ReadinessCheckView.as_view()),

    # Re-fetch saved recommendations (page refresh / back navigation)
    path('discovery/recommendations/',      RecommendationsView.as_view()),

    # Edit answers and re-run matching (context strip "Edit" button)
    path('discovery/recommendations/edit/', EditRecommendationsView.as_view()),

    # Restore questionnaire answers on page load (if localStorage has session_token)
    path('discovery/session/',              SessionResumeView.as_view()),

    # Link anonymous session to a logged-in user account (called after register/login)
    path('discovery/link-session/',         LinkSessionView.as_view()),

    # Custom inquiry form submission (Discover Results page)
    path('discovery/custom-inquiry/',       CustomInquiryView.as_view()),

    # Public studio profile + inquiry submit
    path('discovery/studios/<int:profile_id>/',         PublicStudioProfileView.as_view()),
    path('discovery/studios/<int:profile_id>/inquire/', StudioInquiryView.as_view()),

    # Feature 6 — Studio Directory (public browsable catalog)
    path('studios/directory/', StudioDirectoryView.as_view()),

    # Seller — own studio inquiries only
    path('seller/studio-inquiries/', SellerStudioInquiryView.as_view()),

    # Admin — discovery
    path('admin/discovery/buyers/',                     AdminDiscoveryBuyerListView.as_view()),
    path('admin/discovery/buyers/<uuid:buyer_id>/',     AdminDiscoveryBuyerDetailView.as_view()),
    path('admin/discovery/inquiries/',                  AdminDiscoveryInquiryListView.as_view()),
    path('admin/discovery/studio-inquiries/',           AdminStudioInquiryListView.as_view()),
]