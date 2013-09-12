

def configure_service(config):
    from ichnaea.service.geolocate.views import configure_geolocate
    from ichnaea.service.heartbeat.views import configure_heartbeat

    configure_geolocate(config)
    configure_heartbeat(config)
