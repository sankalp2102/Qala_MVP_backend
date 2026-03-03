# core/middleware.py
from supertokens_python.framework.django.django_middleware import middleware as st_middleware


class SuperTokensSessionMiddleware:
    def __init__(self, get_response):
        self.get_response   = get_response
        self.st_middleware  = st_middleware(get_response)

    def __call__(self, request):
        if request.path.startswith('/auth/'):
            return self.st_middleware(request)
        return self.get_response(request)