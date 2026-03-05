"""
URL configuration for Qala project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# Qala/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # SuperTokens auth routes (/auth/signin, /auth/signout, etc.) are handled
    # automatically by core.middleware.SuperTokensSessionMiddleware — no include needed.
    path('api/',   include('core.urls')),
    path('api/',   include('seller_profile.urls')),
    path('api/',   include('discovery.urls')),
]

# BUG 6 FIX: only serve media files in DEBUG mode (static() is a no-op in prod anyway
# but this makes intent explicit and avoids the unused middleware import)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)