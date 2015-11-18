"""
Common webapp related base views.
"""

from pyramid.httpexceptions import HTTPMethodNotAllowed
from pyramid.response import Response

HTTP_METHODS = frozenset([
    'DELETE',
    'GET',
    'HEAD',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
])


class BaseView(object):
    """
    A base view class supporting route and view configuration based
    on class attributes.
    """

    _cors_headers = None
    cors_max_age = 86400 * 30   #: Cache preflight requests for 30 days.
    cors_origin = '*'  # Allowed CORS origins.
    http_cache = None  #: HTTP cache configuration.
    methods = ('GET', 'HEAD', 'POST')  # Supported HTTP methods.
    renderer = 'json'  #: The name of the renderer to use.
    route = None  #: The url path for this view, e.g. `/hello`.

    @classmethod
    def configure(cls, config):
        """
        Adds a route and a view with a JSON renderer based on the
        class route attribute.

        :param config: The Pyramid main configuration.
        :type config: :class:`pyramid.config.Configurator`
        """
        path = cls.route
        name = path.lstrip('/').replace('/', '_')
        config.add_route(name, path)

        http_methods = cls.methods
        config.add_view(
            cls,
            http_cache=cls.http_cache,
            route_name=name,
            renderer=cls.renderer,
            request_method=http_methods,
        )
        unsupported_methods = HTTP_METHODS - set(http_methods)

        if cls.cors_origin:
            unsupported_methods = unsupported_methods - set(['OPTIONS'])

            config.add_view(
                cls,
                attr='options',
                route_name=name,
                request_method='OPTIONS',
            )
            cls._cors_headers = {
                'Access-Control-Allow-Origin': cls.cors_origin,
            }
            if cls.cors_max_age:
                cls._cors_headers[
                    'Access-Control-Max-Age'] = str(cls.cors_max_age)

        if unsupported_methods:
            config.add_view(
                cls,
                attr='unsupported',
                route_name=name,
                request_method=tuple(unsupported_methods),
            )

    def __init__(self, request):
        """
        Instantiate the view with a request object.
        """
        self.request = request
        if self._cors_headers:
            request.response.headers.update(self._cors_headers)

    def __call__(self):
        """
        Call and execute the view, returning a response.
        """
        raise NotImplementedError()

    def prepare_exception(self, exc):
        """Prepare an exception response."""
        if isinstance(exc, Response) and self._cors_headers:
            exc.headers.update(self._cors_headers)
        return exc

    def options(self):
        """
        Return a response for HTTP OPTIONS requests.
        """
        # TODO: This does not actually parse the Origin header or
        # requested method.
        return Response(headers=self._cors_headers)

    def unsupported(self):
        """
        Return a method not allowed response.
        """
        raise HTTPMethodNotAllowed()
