from pyramid.view import view_config


@view_config(route_name='homepage', renderer='templates/homepage.pt')
def homepage_view(request):
    return {}
