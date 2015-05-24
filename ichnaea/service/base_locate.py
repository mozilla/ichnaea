from ichnaea.models.transform import ReportTransform


class LocateTransform(ReportTransform):

    radio_id = ('radioType', 'radio')
    cell_id = ('cellTowers', 'cell')
    cell_map = [
        # if both radio and radioType are present in the source,
        # radioType takes precedence
        ('radio', 'radio'),
        ('radioType', 'radio'),
        ('mobileCountryCode', 'mcc'),
        ('mobileNetworkCode', 'mnc'),
        ('locationAreaCode', 'lac'),
        ('cellId', 'cid'),
        ('psc', 'psc'),
        ('signalStrength', 'signalStrength'),
        ('timingAdvance', 'timingAdvance'),
    ]

    wifi_id = ('wifiAccessPoints', 'wifi')
    wifi_map = [
        ('macAddress', 'key'),
        ('channel', 'channel'),
        ('signalToNoiseRatio', 'snr'),
        ('signalStrength', 'signal'),
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
