# discovery/urls.py
from django.urls import path
from .views import (
    VisualGridImagesView,
    ReadinessCheckView,
    RecommendationsView,
    EditRecommendationsView,
    SessionResumeView,
    LinkSessionView,
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
]