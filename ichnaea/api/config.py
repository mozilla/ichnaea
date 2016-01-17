"""
API related view configuration.
"""


def configure_api(config):
    """Configure API related views and set up routes."""
    from ichnaea.api.locate.views import (
        LocateV1View,
        LocateV2View,
        RegionV0JSView,
        RegionV0JSONView,
        RegionV1View,
    )
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
