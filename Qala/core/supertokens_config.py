# core/supertokens_config.py
import logging
import httpx
from django.conf import settings
from supertokens_python import init, InputAppInfo, SupertokensConfig
from supertokens_python.recipe import emailpassword, session, userroles, emailverification
from supertokens_python.recipe.emailpassword import InputFormField
from supertokens_python.recipe.emailpassword.interfaces import APIInterface

logger = logging.getLogger('core')


def make_email_password_override(original_impl: APIInterface):
    original_sign_up_post = original_impl.sign_up_post

    async def sign_up_post(
        form_fields,
        tenant_id,
        session,
        should_try_linking_with_session_user,
        api_options,
        user_context,
    ):
        result = await original_sign_up_post(
            form_fields, tenant_id, session,
            should_try_linking_with_session_user,
            api_options, user_context,
        )

        if result.status == 'OK':
            email      = next((f.value for f in form_fields if f.id == 'email'), None)
            st_user_id = result.user.id
            logger.info(f'SuperTokens signup OK — email={email} id={st_user_id}')

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{settings.SUPERTOKENS['API_DOMAIN']}/api/auth/customer-hook/",
                        json={
                            'email':          email,
                            'supertokens_id': st_user_id,
                        },
                        headers={
                            'X-Hook-Secret': settings.SUPERTOKENS_HOOK_SECRET,
                            'Content-Type':  'application/json',
                        },
                    )
                    if resp.status_code != 201:
                        logger.error(f'Customer hook failed: {resp.status_code} — {resp.text}')
            except Exception as e:
                logger.error(f'Customer hook exception: {e}')

        return result

    original_impl.sign_up_post = sign_up_post
    return original_impl


def init_supertokens():
    init(
        app_info=InputAppInfo(
            app_name          = settings.SUPERTOKENS['APP_NAME'],
            api_domain        = settings.SUPERTOKENS['API_DOMAIN'],
            website_domain    = settings.SUPERTOKENS['WEBSITE_DOMAIN'],
            api_base_path     = '/auth',
            website_base_path = '/auth',
        ),
        supertokens_config=SupertokensConfig(
            connection_uri = settings.SUPERTOKENS['SUPERTOKENS_URL'],
            api_key        = settings.SUPERTOKENS['API_KEY'],
        ),
        framework   = 'django',
        recipe_list = [
            session.init(
                cookie_secure               = not settings.DEBUG,
                cookie_same_site            = 'lax',
                anti_csrf                   = 'DVCS',
                session_expired_status_code = 401,
            ),
            emailverification.init(mode='REQUIRED'),
            emailpassword.init(
                sign_up_feature=emailpassword.InputSignUpFeature(
                    form_fields=[
                        InputFormField(id='email'),
                        InputFormField(id='password'),
                    ]
                ),
                override=emailpassword.InputOverrideConfig(
                    apis=make_email_password_override,
                ),
            ),
            userroles.init(),
        ],
        mode = 'wsgi',
    )