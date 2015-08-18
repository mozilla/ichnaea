from inspect import ismethod
import uuid

import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory.base import Factory
from factory import fuzzy

from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.models import (
    ApiKey,
    Cell,
    CellArea,
    CellBlocklist,
    CellObservation,
    OCIDCell,
    OCIDCellArea,
    Radio,
    Wifi,
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
    log = True
    allow_fallback = False

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
    range = LAC_MIN_ACCURACY


class CellKeyFactory(CellAreaKeyFactory):

    cid = fuzzy.FuzzyInteger(1, 60000)


class CellPositionFactory(CellKeyFactory, CellAreaPositionFactory):

    psc = fuzzy.FuzzyInteger(1, 500)
    range = CELL_MIN_ACCURACY


class CellFactory(CellPositionFactory, BboxFactory, BaseSQLFactory):

    class Meta:
        model = Cell.create


class CellAreaFactory(CellAreaPositionFactory, BboxFactory, BaseSQLFactory):

    class Meta:
        model = CellArea.create


class CellBlocklistFactory(CellKeyFactory, BaseSQLFactory):

    class Meta:
        model = CellBlocklist


class OCIDCellFactory(CellPositionFactory, BaseSQLFactory):

    class Meta:
        model = OCIDCell.create


class OCIDCellAreaFactory(CellAreaPositionFactory, BaseSQLFactory):

    class Meta:
        model = OCIDCellArea.create


class CellObservationFactory(CellPositionFactory, BaseMemoryFactory):

    class Meta:
        model = CellObservation.create


class WifiKeyFactory(Factory):

    key = FuzzyWifiKey()


class WifiPositionFactory(WifiKeyFactory):

    lat = GB_LAT
    lon = GB_LON
    range = WIFI_MIN_ACCURACY


class WifiFactory(WifiPositionFactory, BboxFactory, BaseSQLFactory):

    class Meta:
        model = Wifi.create


class WifiMacFactory(Factory):

    mac = FuzzyWifiMac()


class WifiShardFactory(WifiMacFactory, BaseSQLFactory):

    lat = GB_LAT
    lon = GB_LON
    radius = WIFI_MIN_ACCURACY

    class Meta:
        model = WifiShard.create


class WifiObservationFactory(WifiPositionFactory, BaseMemoryFactory):

    class Meta:
        model = WifiObservation.create
