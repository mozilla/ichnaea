

class BaseView(object):

    route = None

    @classmethod
    def configure(cls, config):
        path = cls.route
        name = path.lstrip('/').replace('/', '_')
        config.add_route(name, path)
        config.add_view(cls, route_name=name, renderer='json')

    def __init__(self, request):
        self.request = request

    def __call__(self):  # pragma: no cover
        raise NotImplementedError()
