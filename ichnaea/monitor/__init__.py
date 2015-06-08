

def configure_monitor(config):
    from ichnaea.monitor.views import HeartbeatView
    from ichnaea.monitor.views import MonitorView

    HeartbeatView.configure(config)
    MonitorView.configure(config)
