# core/utils.py
import logging
from rest_framework.views import exception_handler

logger = logging.getLogger('core')


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            'status':  'error',
            'message': '',
            'code':    response.status_code,
        }
        if isinstance(response.data, dict):
            error_data['message'] = response.data.get('detail', str(response.data))
            if isinstance(error_data['message'], dict):
                error_data['details'] = error_data['message']
                error_data['message'] = 'Validation error'
        elif isinstance(response.data, list):
            error_data['message'] = str(response.data[0]) if response.data else 'Error'
        else:
            error_data['message'] = str(response.data)

        response.data = error_data

    return response