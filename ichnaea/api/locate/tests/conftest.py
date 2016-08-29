import pytest

from ichnaea.api.locate.tests.base import DummyModel


@pytest.fixture(scope='class')
def cls_source(request, data_queues, geoip_db, http_session,
               raven_client, redis_client, stats_client):
    source = request.cls.Source(
        geoip_db=geoip_db,
        raven_client=raven_client,
        redis_client=redis_client,
        stats_client=stats_client,
        data_queues=data_queues,
    )
    yield source


@pytest.fixture(scope='function')
def source(cls_source, raven, redis, stats):
    yield cls_source


@pytest.fixture(scope='session')
def bhutan_model(geoip_data):
    bhutan = geoip_data['Bhutan']
    yield DummyModel(
        lat=bhutan['latitude'],
        lon=bhutan['longitude'],
        radius=bhutan['radius'],
        code=bhutan['region_code'],
        name=bhutan['region_name'],
        ip=bhutan['ip'])


@pytest.fixture(scope='session')
def london_model(geoip_data):
    london = geoip_data['London']
    yield DummyModel(
        lat=london['latitude'],
        lon=london['longitude'],
        radius=london['radius'],
        code=london['region_code'],
        name=london['region_name'],
        ip=london['ip'])


@pytest.fixture(scope='session')
def london2_model(geoip_data):
    london = geoip_data['London2']
    yield DummyModel(
        lat=london['latitude'],
        lon=london['longitude'],
        radius=london['radius'],
        code=london['region_code'],
        name=london['region_name'],
        ip=london['ip'])
