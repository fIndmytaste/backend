from rest_framework.renderers import JSONRenderer


class UTF8JSONRenderer(JSONRenderer):
    """
    JSON renderer that outputs proper UTF-8 characters instead of
    escaped unicode sequences (e.g. apostrophes in names show as ' not \\u2019).
    """
    charset = 'utf-8'
    ensure_ascii = False

    def render(self, data, accepted_media_type=None, renderer_context=None):
        self.ensure_ascii = False
        return super().render(data, accepted_media_type, renderer_context)
