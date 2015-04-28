import urlparse

EXPORT_QUEUE_PREFIX = 'queue_export_'
_sentinel = object()


class ExportQueue(object):

    def __init__(self, name, settings):
        self.name = name
        self.settings = settings
        self.batch = int(settings.get('batch', -1))
        self.url = settings.get('url', '') or ''
        self.scheme = urlparse.urlparse(self.url).scheme
        self.source_apikey = settings.get('source_apikey', _sentinel)

    @property
    def monitor_name(self):
        return self.queue_key()

    def queue_key(self, api_key=None):
        return EXPORT_QUEUE_PREFIX + self.name

    def export_allowed(self, api_key):
        return (api_key != self.source_apikey)


def configure_export(app_config):
    export_queues = {}
    for section_name in app_config.sections():
        if section_name.startswith('export:'):
            section = app_config.get_map(section_name)
            name = section_name.split(':')[1]
            export_queues[name] = ExportQueue(name, section)
    return export_queues
