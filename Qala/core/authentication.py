# core/authentication.py
import logging
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from supertokens_python.recipe.session.syncio import get_session
from supertokens_python.recipe.session.exceptions import (
    UnauthorisedError,          # was: UnauthorisedException
    TokenTheftError,            # was: TokenTheftDetectedException
    TryRefreshTokenError,       # was: TryRefreshTokenException
)
from .models import User

logger = logging.getLogger('core')


class SuperTokensAuthentication(BaseAuthentication):

    def authenticate(self, request):
        try:
            session = get_session(request, session_required=False)
        except TryRefreshTokenError:
            raise AuthenticationFailed(
                detail={'message': 'Session expired. Please refresh.', 'code': 'TRY_REFRESH_TOKEN'},
                code=401,
            )
        except TokenTheftError:
            raise AuthenticationFailed(
                detail={'message': 'Token theft detected. Please log in again.', 'code': 'TOKEN_THEFT'},
                code=401,
            )
        except UnauthorisedError:
            raise AuthenticationFailed(
                detail={'message': 'Invalid or expired session.', 'code': 'UNAUTHORISED'},
                code=401,
            )
        except Exception as e:
            logger.warning(f'SuperTokens auth error: {e}')
            return None

        if session is None:
            return None

        supertokens_id = session.get_user_id()

        try:
            user = User.objects.select_related(
                'admin_profile',
                'seller_account',
                'customer_profile',
            ).get(supertokens_id=supertokens_id)
        except User.DoesNotExist:
            logger.error(f'SuperTokens user {supertokens_id} has no Django User record')
            raise AuthenticationFailed(
                detail={'message': 'User account not found.', 'code': 'USER_NOT_FOUND'},
                code=401,
            )

        if not user.is_active:
            raise AuthenticationFailed(
                detail={'message': 'Account is disabled.', 'code': 'ACCOUNT_DISABLED'},
                code=401,
            )

        request.supertokens_session = session
        return (user, None)

    def authenticate_header(self, request):
        return 'SuperTokens'