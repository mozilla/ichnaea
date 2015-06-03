def configure_service(config):
    from ichnaea.service.country.views import CountryView
    from ichnaea.service.geosubmit.views import GeoSubmitView
    from ichnaea.service.geosubmit2.views import GeoSubmit2View
    from ichnaea.service.heartbeat.views import HeartbeatView
    from ichnaea.service.monitor.views import MonitorView
    from ichnaea.service.locate1.views import Locate1View
    from ichnaea.service.locate2.views import Locate2View
    from ichnaea.service.submit.views import SubmitView

    CountryView.configure(config)
    GeoSubmitView.configure(config)
    GeoSubmit2View.configure(config)
    HeartbeatView.configure(config)
    Locate1View.configure(config)
    Locate2View.configure(config)
    MonitorView.configure(config)
    SubmitView.configure(config)
