def configure_service(config):
    from ichnaea.service.geolocate.views import configure_geolocate
    from ichnaea.service.geosubmit.views import configure_geosubmit
    from ichnaea.service.heartbeat.views import configure_heartbeat
    from ichnaea.service.search.views import configure_search
    from ichnaea.service.submit.views import configure_submit

    configure_geolocate(config)
    configure_geosubmit(config)
    configure_heartbeat(config)
    configure_search(config)
    configure_submit(config)
