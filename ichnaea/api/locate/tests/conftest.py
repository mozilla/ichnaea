import pytest

from ichnaea.api.locate.tests.base import DummyModel
from ichnaea.tests.base import GEOIP_DATA


@pytest.fixture(scope='class')
def source(request, geoip_db, raven_client,
           redis_client, stats_client, data_queues):
    request.cls.source = request.cls.Source(
        geoip_db=geoip_db,
        raven_client=raven_client,
        redis_client=redis_client,
        stats_client=stats_client,
        data_queues=data_queues,
    )
    bhutan = GEOIP_DATA['Bhutan']
    request.cls.bhutan_model = DummyModel(
        lat=bhutan['latitude'],
        lon=bhutan['longitude'],
        radius=bhutan['radius'],
        code=bhutan['region_code'],
        name=bhutan['region_name'],
        ip=bhutan['ip'])
    london = GEOIP_DATA['London']
    request.cls.london_model = DummyModel(
        lat=london['latitude'],
        lon=london['longitude'],
        radius=london['radius'],
        code=london['region_code'],
        name=london['region_name'],
        ip=london['ip'])
