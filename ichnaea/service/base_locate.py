from ichnaea.models.transform import ReportTransform


class LocateTransform(ReportTransform):

    radio_id = ('radioType', 'radio')
    cell_id = ('cellTowers', 'cell')
    cell_map = [
        ('radio', 'radio', None),
        ('radioType', 'radio', None),
        ('mobileCountryCode', 'mcc', None),
        ('mobileNetworkCode', 'mnc', None),
        ('locationAreaCode', 'lac', None),
        ('cellId', 'cid', None),
        ('psc', 'psc', None),
        ('signalStrength', 'signalStrength', None),
        ('timingAdvance', 'timingAdvance', None),
    ]

    wifi_id = ('wifiAccessPoints', 'wifi')
    wifi_map = [
        ('macAddress', 'key', None),
        ('channel', 'channel', None),
        ('signalToNoiseRatio', 'snr', None),
        ('signalStrength', 'signal', None),
    ]


def prepare_locate_query(request_data, client_addr=None):
    """
    Transform a geolocate API dictionary to an equivalent internal
    locate query dictionary.
    """
    transform = LocateTransform()
    parsed_data = transform.transform_one(request_data)

    query = {'geoip': client_addr}
    query['cell'] = parsed_data.get('cell', [])
    query['wifi'] = parsed_data.get('wifi', [])
    return query
