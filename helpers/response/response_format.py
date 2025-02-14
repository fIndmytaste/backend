from rest_framework.response import Response
from rest_framework import status
from .code import status_code
from .pagination import Paginator


class DataResponse:
    def __init__(self, success: bool = True, message: str = None, code: int = None, response_code: str = None):

        self.success = success
        self.message = message
        self.response_code = response_code
        self._code = status_code()[code]

    def result(self):
        data = dict(
            success=self.success,
            response_code=self.response_code,
            response=self.message
        )
        return Response(data=data, status=self._code)
    





def error_response(message='An error occurred', group='BAD_REQUEST', status_code=400):
    response_data = {'status': False, 'group': group, 'detail': message, 'message': message}
    return Response(response_data, status=status_code)


def validation_error_response(errors=None):
    message = "validation failed"
    response_data = {'status': False,'message': message, 'detail': message, 'errors': errors}
    return Response(response_data, status=status.HTTP_422_UNPROCESSABLE_ENTITY)



def success_response(data=None, message='Success',  status_code=200):
    response_data = {'status': True, 'message': message,'detail': message,'data': data}
    return Response(response_data, status=status_code)


def verification_success_response(data=None, message='Success', response_code='00', status_code=200,status_bool=True):
    response_data = {'status': status_bool, 'message': message,'detail': message,"response_code":response_code, 'data': data}
    return Response(response_data, status=status_code)

def bad_request_response(message='Bad Request', group='BAD_REQUEST', status_code=400):
    return error_response(message, group , status_code)


def internal_server_error_response(message='Internal Server Error', status_code=500):
    return error_response(message, None, status_code)



def paginate_success_response(request, data=[],page_size=10):
    paginator = Paginator(data,request)
    return paginator.paginate(page_size)