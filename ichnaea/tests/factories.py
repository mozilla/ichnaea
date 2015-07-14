from inspect import ismethod

import factory
from factory.alchemy import SQLAlchemyModelFactory
from factory import fuzzy

from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlacklist,
    CellObservation,
    OCIDCell,
    OCIDCellArea,
    Radio,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea.tests.base import (
    GB_LAT,
    GB_LON,
    GB_MCC,
    GB_MNC,
    SESSION,
)


class BaseFactory(SQLAlchemyModelFactory):

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


class FuzzyWifiKey(fuzzy.BaseFuzzyAttribute):

    def fuzz(self):
        num = fuzzy.random.randint(100000, 999999)
        return 'a82066{num:06d}'.format(num=num)


class BboxFactory(BaseFactory):

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


class CellAreaKeyFactory(BaseFactory):

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


class CellFactory(CellPositionFactory, BboxFactory):

    class Meta:
        model = Cell.create


class CellAreaFactory(CellAreaPositionFactory, BboxFactory):

    class Meta:
        model = CellArea.create


class CellBlacklistFactory(CellKeyFactory):

    class Meta:
        model = CellBlacklist


class OCIDCellFactory(CellPositionFactory):

    class Meta:
        model = OCIDCell.create


class OCIDCellAreaFactory(CellAreaPositionFactory):

    class Meta:
        model = OCIDCellArea.create


class CellObservationFactory(CellPositionFactory):

    class Meta:
        model = CellObservation.create


class WifiKeyFactory(BaseFactory):

    key = FuzzyWifiKey()


class WifiPositionFactory(WifiKeyFactory):

    lat = GB_LAT
    lon = GB_LON
    range = WIFI_MIN_ACCURACY


class WifiFactory(WifiPositionFactory, BboxFactory):

    class Meta:
        model = Wifi.create


class WifiBlacklistFactory(WifiKeyFactory):

    class Meta:
        model = WifiBlacklist


class WifiObservationFactory(WifiPositionFactory):

    class Meta:
        model = WifiObservation.create
