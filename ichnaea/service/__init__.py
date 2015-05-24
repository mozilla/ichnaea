def configure_service(config):
    from ichnaea.service.country.views import configure_country
    from ichnaea.service.geolocate.views import configure_geolocate
    from ichnaea.service.geosubmit.views import configure_geosubmit
    from ichnaea.service.geosubmit2.views import configure_geosubmit2
    from ichnaea.service.heartbeat.views import configure_heartbeat
    from ichnaea.service.monitor.views import configure_monitor
    from ichnaea.service.search.views import configure_search
    from ichnaea.service.submit.views import configure_submit

    configure_country(config)
    configure_geolocate(config)
    configure_geosubmit(config)
    configure_geosubmit2(config)
    configure_heartbeat(config)
    configure_monitor(config)
    configure_search(config)
    configure_submit(config)
