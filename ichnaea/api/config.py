"""
API related view configuration.
"""


def configure_api(config):
    """Configure API related views and set up routes."""
    from ichnaea.api.locate.locate_v1.views import LocateV1View
    from ichnaea.api.locate.locate_v2.views import LocateV2View
    from ichnaea.api.locate.region.views import RegionView
    from ichnaea.api.submit.submit_v1.views import SubmitV1View
    from ichnaea.api.submit.submit_v2.views import SubmitV2View
    from ichnaea.api.submit.submit_v3.views import SubmitV3View

    LocateV1View.configure(config)
    LocateV2View.configure(config)
    RegionView.configure(config)
    SubmitV1View.configure(config)
    SubmitV2View.configure(config)
    SubmitV3View.configure(config)
