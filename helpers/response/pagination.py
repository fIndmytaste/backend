from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class CustomPagination(PageNumberPagination):
    def get_paginated_response(self, data, is_filter=False):
        return Response({
            'metadata': {
                'count': self.page.paginator.count,
                'is_filter': is_filter,
                "has_records": True if (self.page.paginator.count > 0 and is_filter) or self.page.paginator.count > 0 else False,
                'page_size': self.page_size,
                'page': self.page.number,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'results': data
        })

class Paginator:
    paginator = CustomPagination()

    def __init__(self, records, request):
        """
        Method that paginate all the records
        """
        self.records = records
        self.request = request

    def paginate(self, no_of_record: int):
        self.paginator.page_size = no_of_record
        result_page = self.paginator.paginate_queryset(self.records, self.request)
        return self.paginator.get_paginated_response(result_page)
    




class PaginatorCustom:
    paginator = CustomPagination()

    def __init__(self, records, request, serialize_func, func_param={}, is_filter=False):
        """
        Initialize the paginator with a queryset, request, and a dynamic serialization function.
        :param records: The queryset or list of records to paginate
        :param request: The request object for pagination context
        :param serialize_func: A callable function that handles serialization for each record
        """
        self.records = records
        self.request = request
        self.serialize_func = serialize_func 
        self.func_param = func_param
        self.is_filter = is_filter

    def paginate(self, no_of_record: int):
        """
        Paginate the records based on the provided page size.
        :param no_of_record: The number of records per page
        """
        self.paginator.page_size = no_of_record
        result_page = self.paginator.paginate_queryset(self.records, self.request)

        print(len(result_page))
        # Apply the dynamic serialization function to each record in the paginated result
        serialized_data = [self.serialize_func(record,**self.func_param) for record in result_page]
        return self.paginator.get_paginated_response(serialized_data, self.is_filter)
