from inspect import ismethod
import uuid

import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory.base import Factory
from factory import fuzzy

from ichnaea.api.locate.constants import (
    BLUE_MIN_ACCURACY,
    CELL_MIN_ACCURACY,
    CELLAREA_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.conftest import (
    GB_LAT,
    GB_LON,
    GB_MCC,
    GB_MNC,
    SESSION,
)
from ichnaea.models import (
    ApiKey,
    BlueObservation,
    BlueShard,
    CellArea,
    CellAreaOCID,
    CellObservation,
    CellShard,
    CellShardOCID,
    ExportConfig,
    Radio,
    RegionStat,
    ReportSource,
    WifiShard,
    WifiObservation,
)
from ichnaea import util


class BaseMemoryFactory(Factory):

    class Meta:
        strategy = factory.CREATE_STRATEGY

    @classmethod
    def _create(cls, constructor, *args, **kwargs):
        """Create an instance of the model, and save it to the database."""
        if ismethod(constructor) and '_raise_invalid' not in kwargs:
            kwargs['_raise_invalid'] = True
        return constructor(*args, **kwargs)


class BaseSQLFactory(SQLAlchemyModelFactory):

    class Meta:
        strategy = factory.CREATE_STRATEGY

    @classmethod
    def _create(cls, constructor, session=None, *args, **kwargs):
        """Create an instance of the model, and save it to the database."""
        if ismethod(constructor) and '_raise_invalid' not in kwargs:
            kwargs['_raise_invalid'] = True
        obj = constructor(*args, **kwargs)
        if session is None:
            session = SESSION['default']
        session.add(obj)
        return obj


class FuzzyUUID(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        return uuid.uuid4().hex


class FuzzyMacKey(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        num = fuzzy.random.randint(100000, 999999)
        return 'a82066{num:06d}'.format(num=num)


class FuzzyMac(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        num = fuzzy.random.randint(10000000, 99999999)
        return 'a820{num:08d}'.format(num=num)


class ApiKeyFactory(BaseSQLFactory):

    class Meta:
        model = ApiKey

    valid_key = FuzzyUUID()
    maxreq = 0
    allow_fallback = False
    allow_locate = True
    allow_transfer = False

    fallback_name = 'fall'
    fallback_url = 'http://127.0.0.1:9/?api'
    fallback_ratelimit = 10
    fallback_ratelimit_interval = 60
    fallback_cache_expire = 60

    store_sample_locate = 100
    store_sample_submit = 100


class BboxFactory(Factory):

    @factory.lazy_attribute
    def min_lat(self):
        return self.lat

    @factory.lazy_attribute
    def max_lat(self):
        return self.lat

    @factory.lazy_attribute
    def min_lon(self):
        return self.lon

    @factory.lazy_attribute
    def max_lon(self):
        return self.lon


class BlueShardFactory(BaseSQLFactory):

    mac = FuzzyMac()
    lat = GB_LAT
    lon = GB_LON
    radius = BLUE_MIN_ACCURACY / 2.0
    region = 'GB'
    samples = 1
    source = ReportSource.gnss
    weight = 1.0
    created = util.utcnow()
    modified = util.utcnow()
    last_seen = util.utcnow().date()

    class Meta:
        model = BlueShard.create


class BlueObservationFactory(BaseMemoryFactory):

    mac = FuzzyMacKey()
    lat = GB_LAT
    lon = GB_LON
    accuracy = 10.0
    signal = -80
    snr = 30
    source = ReportSource.gnss

    class Meta:
        model = BlueObservation.create


class CellAreaKeyFactory(Factory):

    radio = fuzzy.FuzzyChoice([Radio.gsm, Radio.wcdma, Radio.lte])
    mcc = GB_MCC
    mnc = GB_MNC
    lac = fuzzy.FuzzyInteger(1, 60000)


class CellAreaPositionFactory(CellAreaKeyFactory):

    lat = GB_LAT
    lon = GB_LON


class CellKeyFactory(CellAreaKeyFactory):

    cid = fuzzy.FuzzyInteger(1, 60000)


class CellPositionFactory(CellKeyFactory, CellAreaPositionFactory):

    psc = fuzzy.FuzzyInteger(1, 500)


class BaseCellShardFactory(CellPositionFactory, BboxFactory):

    radius = CELL_MIN_ACCURACY / 2.0
    region = 'GB'
    samples = 1
    source = ReportSource.gnss
    weight = 1.0
    created = util.utcnow()
    modified = util.utcnow()
    last_seen = util.utcnow().date()


class CellShardFactory(BaseCellShardFactory, BaseSQLFactory):

    class Meta:
        model = CellShard.create


class CellShardOCIDFactory(BaseCellShardFactory, BaseSQLFactory):

    class Meta:
        model = CellShardOCID.create


class CellAreaFactory(CellAreaPositionFactory, BboxFactory, BaseSQLFactory):

    radius = CELLAREA_MIN_ACCURACY / 2.0
    region = 'GB'
    avg_cell_radius = CELL_MIN_ACCURACY / 2.0
    num_cells = 1
    created = util.utcnow()
    modified = util.utcnow()
    last_seen = util.utcnow().date()

    class Meta:
        model = CellArea.create


class CellAreaOCIDFactory(CellAreaPositionFactory,
                          BboxFactory, BaseSQLFactory):

    radius = CELLAREA_MIN_ACCURACY / 2.0
    region = 'GB'
    avg_cell_radius = CELL_MIN_ACCURACY / 2.0
    num_cells = 1
    created = util.utcnow()
    modified = util.utcnow()
    last_seen = util.utcnow().date()

    class Meta:
        model = CellAreaOCID.create


class CellObservationFactory(CellPositionFactory, BaseMemoryFactory):

    class Meta:
        model = CellObservation.create

    accuracy = 10.0
    source = ReportSource.gnss

    @factory.lazy_attribute
    def signal(self):
        if self.radio is Radio.gsm:
            return -95
        if self.radio is Radio.wcdma:
            return -100
        if self.radio is Radio.lte:
            return -105


class ExportConfigFactory(BaseSQLFactory):

    class Meta:
        model = ExportConfig

    name = FuzzyUUID()
    batch = 100
    schema = 'dummy'
    url = None
    skip_keys = frozenset()


class RegionStatFactory(BaseSQLFactory):

    class Meta:
        model = RegionStat

    region = 'GB'
    gsm = 0
    wcdma = 0
    lte = 0
    wifi = 0


class WifiShardFactory(BaseSQLFactory):

    mac = FuzzyMac()
    lat = GB_LAT
    lon = GB_LON
    radius = WIFI_MIN_ACCURACY / 2.0
    region = 'GB'
    samples = 1
    source = ReportSource.gnss
    weight = 1.0
    created = util.utcnow()
    modified = util.utcnow()
    last_seen = util.utcnow().date()

    class Meta:
        model = WifiShard.create


class WifiObservationFactory(BaseMemoryFactory):

    mac = FuzzyMacKey()
    lat = GB_LAT
    lon = GB_LON
    accuracy = 10.0
    signal = -80
    snr = 30
    source = ReportSource.gnss

    class Meta:
        model = WifiObservation.create
