from inspect import ismethod
import uuid

import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory.base import Factory
from factory import fuzzy

from ichnaea.api.locate.constants import (
    CELL_MIN_ACCURACY,
    CELLAREA_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.models import (
    ApiKey,
    CellArea,
    CellAreaOCID,
    CellObservation,
    CellOCID,
    CellShard,
    Radio,
    RegionStat,
    WifiShard,
    WifiObservation,
)
from ichnaea.tests.base import (
    GB_LAT,
    GB_LON,
    GB_MCC,
    GB_MNC,
    SESSION,
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
    def _create(cls, constructor, _session=None, *args, **kwargs):
        """Create an instance of the model, and save it to the database."""
        if ismethod(constructor) and '_raise_invalid' not in kwargs:
            kwargs['_raise_invalid'] = True
        obj = constructor(*args, **kwargs)
        if _session is None:
            _session = SESSION['default']
        _session.add(obj)
        return obj


class FuzzyUUID(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        return uuid.uuid4().hex


class FuzzyWifiKey(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        num = fuzzy.random.randint(100000, 999999)
        return 'a82066{num:06d}'.format(num=num)


class FuzzyWifiMac(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        num = fuzzy.random.randint(10000000, 99999999)
        return 'a820{num:08d}'.format(num=num)


class ApiKeyFactory(BaseSQLFactory):

    class Meta:
        model = ApiKey

    valid_key = FuzzyUUID()
    maxreq = 0
    log_locate = True
    log_region = True
    log_submit = True
    allow_fallback = False
    allow_locate = True

    @factory.lazy_attribute
    def shortname(self):
        return self.valid_key


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


class CellShardFactory(CellPositionFactory, BboxFactory, BaseSQLFactory):

    radius = CELL_MIN_ACCURACY / 2.0
    region = 'GB'
    samples = 1
    created = util.utcnow()
    modified = util.utcnow()

    class Meta:
        model = CellShard.create


class CellOCIDFactory(CellPositionFactory, BboxFactory, BaseSQLFactory):

    radius = CELL_MIN_ACCURACY / 2.0
    region = 'GB'
    samples = 1
    created = util.utcnow()
    modified = util.utcnow()

    class Meta:
        model = CellOCID.create


class CellAreaFactory(CellAreaPositionFactory, BboxFactory, BaseSQLFactory):

    radius = CELLAREA_MIN_ACCURACY / 2.0
    region = 'GB'
    avg_cell_radius = CELL_MIN_ACCURACY / 2.0
    num_cells = 1
    created = util.utcnow()
    modified = util.utcnow()

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

    class Meta:
        model = CellAreaOCID.create


class CellObservationFactory(CellPositionFactory, BaseMemoryFactory):

    class Meta:
        model = CellObservation.create

    accuracy = 10.0

    @factory.lazy_attribute
    def signal(self):
        if self.radio is Radio.gsm:
            return -95
        if self.radio is Radio.wcdma:
            return -100
        if self.radio is Radio.lte:
            return -105
        return None


class RegionStatFactory(BaseSQLFactory):

    class Meta:
        model = RegionStat

    region = 'GB'
    gsm = 0
    wcdma = 0
    lte = 0
    wifi = 0


class WifiShardFactory(BaseSQLFactory):

    mac = FuzzyWifiMac()
    lat = GB_LAT
    lon = GB_LON
    radius = WIFI_MIN_ACCURACY / 2.0
    region = 'GB'
    samples = 1
    created = util.utcnow()
    modified = util.utcnow()

    class Meta:
        model = WifiShard.create


class WifiObservationFactory(BaseMemoryFactory):

    key = FuzzyWifiKey()
    lat = GB_LAT
    lon = GB_LON
    range = WIFI_MIN_ACCURACY / 2.0
    accuracy = 10.0
    signal = -80
    snr = 30

    class Meta:
        model = WifiObservation.create
