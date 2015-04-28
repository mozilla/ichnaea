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
        if self.scheme == 's3':
            return None
        return self.queue_key()

    def queue_key(self, api_key=None):
        if self.scheme == 's3':
            if not api_key:
                api_key = 'no_key'
            return self.queue_prefix + api_key
        return EXPORT_QUEUE_PREFIX + self.name

    @property
    def queue_prefix(self):
        if self.scheme == 's3':
            return EXPORT_QUEUE_PREFIX + self.name + ':'
        return None

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
