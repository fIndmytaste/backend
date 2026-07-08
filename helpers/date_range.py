from datetime import datetime


def parse_date_range(request, start_param='start_date', end_param='end_date'):
    """
    Parse optional `start_date` / `end_date` (YYYY-MM-DD) query params.
    Returns a (start, end) tuple of date objects; either may be None when
    the param is absent or malformed.
    """
    def _parse(name):
        raw = (request.GET.get(name) or '').strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            return None

    return _parse(start_param), _parse(end_param)


def filter_by_date_range(request, queryset, field='created_at'):
    """
    Apply an inclusive created-at date range filter to a queryset based on
    `start_date` / `end_date` query params. No-op when neither is provided.
    """
    start, end = parse_date_range(request)
    if start:
        queryset = queryset.filter(**{f'{field}__date__gte': start})
    if end:
        queryset = queryset.filter(**{f'{field}__date__lte': end})
    return queryset
