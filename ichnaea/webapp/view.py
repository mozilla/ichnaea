"""
Common webapp related base views.
"""


class BaseView(object):
    """
    A base view class supporting route and view configuration based
    on class attributes.
    """

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
        config.add_view(cls, route_name=name, renderer=cls.renderer)

    def __init__(self, request):
        """
        Instantiate the view with a request object.
        """
        self.request = request

    def __call__(self):
        """
        Call and execute the view, returning a response.
        """
        raise NotImplementedError()
