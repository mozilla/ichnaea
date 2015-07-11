"""
Implementation of the public HTTP APIs.
"""


def configure_api(config):
    from ichnaea.api.locate.country.views import CountryView
    from ichnaea.api.locate.locate_v2.views import LocateV2View
    from ichnaea.api.locate.locate_v1.views import LocateV1View
    from ichnaea.api.submit.submit_v1.views import SubmitV1View
    from ichnaea.api.submit.submit_v2.views import SubmitV2View
    from ichnaea.api.submit.submit_v3.views import SubmitV3View

    CountryView.configure(config)
    LocateV1View.configure(config)
    LocateV2View.configure(config)
    SubmitV1View.configure(config)
    SubmitV2View.configure(config)
    SubmitV3View.configure(config)
