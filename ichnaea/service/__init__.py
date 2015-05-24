def configure_service(config):
    from ichnaea.service.country.views import CountryView
    from ichnaea.service.geolocate.views import GeolocateView
    from ichnaea.service.geosubmit.views import GeoSubmitView
    from ichnaea.service.geosubmit2.views import GeoSubmit2View
    from ichnaea.service.heartbeat.views import HeartbeatView
    from ichnaea.service.monitor.views import MonitorView
    from ichnaea.service.search.views import SearchView
    from ichnaea.service.submit.views import SubmitView

    CountryView.configure(config)
    GeolocateView.configure(config)
    GeoSubmitView.configure(config)
    GeoSubmit2View.configure(config)
    HeartbeatView.configure(config)
    MonitorView.configure(config)
    SearchView.configure(config)
    SubmitView.configure(config)
