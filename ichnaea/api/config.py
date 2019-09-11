"""
API related view configuration.
"""


def configure_api(config):
    """Configure API related views and set up routes."""
    from ichnaea.api.locate.views import LocateV0View, LocateV1View, RegionV1View
    from ichnaea.api.submit.views import SubmitV0View, SubmitV1View, SubmitV2View

    LocateV0View.configure(config)
    LocateV1View.configure(config)
    RegionV1View.configure(config)
    SubmitV0View.configure(config)
    SubmitV1View.configure(config)
    SubmitV2View.configure(config)
