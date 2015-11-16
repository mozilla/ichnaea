from six import string_types


class JSRenderer(object):
    """A text-as-JS renderer."""

    def __call__(self, info):
        # see also pyramid.renderers.string_renderer_factory
        def _render(value, system):
            if not isinstance(value, string_types):
                value = str(value)
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'text/javascript'
            return value
        return _render
