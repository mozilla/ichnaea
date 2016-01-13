"""
API related view configuration.
"""


def configure_api(config):
    """Configure API related views and set up routes."""
    from ichnaea.api.locate.locate_v1.views import LocateV1View
    from ichnaea.api.locate.locate_v2.views import LocateV2View
    from ichnaea.api.locate.region_v0.views import RegionV0JSView
    from ichnaea.api.locate.region_v0.views import RegionV0JSONView
    from ichnaea.api.locate.region_v1.views import RegionV1View
    from ichnaea.api.submit.views import (
        SubmitV1View,
        SubmitV2View,
        SubmitV3View,
    )

    LocateV1View.configure(config)
    LocateV2View.configure(config)
    RegionV0JSView.configure(config)
    RegionV0JSONView.configure(config)
    RegionV1View.configure(config)
    SubmitV1View.configure(config)
    SubmitV2View.configure(config)
    SubmitV3View.configure(config)
