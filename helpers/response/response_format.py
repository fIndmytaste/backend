from rest_framework.response import Response
from rest_framework import status
from .code import status_code
from .pagination import Paginator
from urllib.parse import urlencode

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
    





def error_response(message='An error occurred', group='BAD_REQUEST', status_code=400, data=None):
    response_data = {'status': False, 'group': group, 'detail': message, 'message': message, "data":data}
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

def bad_request_response(message='Bad Request', group='BAD_REQUEST', status_code=400, data=None):
    return error_response(message, group , status_code, data)


def internal_server_error_response(message='Internal Server Error', status_code=500):
    return error_response(message, None, status_code)



def paginate_success_response(request, data=[],page_size=10):
    paginator = Paginator(data,request)
    return paginator.paginate(page_size)




def paginate_success_response_with_serializer(request, serializer, data=[], page_size=10, addition_serializer_data=None):
    from django.core.paginator import Paginator, EmptyPage
    # Step 1: Set up the paginator
    paginator = Paginator(data, page_size)
    page_number = request.GET.get('page', 1)  # Default to page 1 if no page is provided
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)  # Return the last page if the page number is out of range
    
    # Step 2: Serialize the paginated data
    transactions_serializer = serializer(page.object_list, many=True, context={'request': request,'addition_serializer_data':addition_serializer_data})

    # Step 3: Build URLs for the next and previous pages
    base_url = request.build_absolute_uri(request.path)  # Get the base URL (the current request's URL)
    query_params = request.GET.dict()  # Get current query params

    # Prepare next and previous links
    next_link = None
    previous_link = None
    
    # Add page size to the query params (if it's not already included)
    query_params['page_size'] = page_size

    if page.has_next():
        query_params['page'] = page.next_page_number()
        next_link = f"{base_url}?{urlencode(query_params)}"  # Construct the next page link
    
    if page.has_previous():
        query_params['page'] = page.previous_page_number()
        previous_link = f"{base_url}?{urlencode(query_params)}"  # Construct the previous page link

    # Step 4: Prepare the response format
    response_data = {
        'metadata': {
            'count': paginator.count,  # Total number of records
            'is_filter': bool(data),  # If data is filtered, set this to True (you can adjust this logic)
            'has_records': True if paginator.count > 0 else False,  # Whether there are records
            'page_size': page_size,  # The size of each page
            'page': page.number,  # Current page number
            'next': next_link,  # Next page link
            'previous': previous_link,  # Previous page link
        },
        'results': transactions_serializer.data  # Serialized results for the current page
    }

    return Response(response_data)





def paginate_success_response(request, data=[],page_size=10):
    paginator = Paginator(data,request)
    return paginator.paginate(page_size)