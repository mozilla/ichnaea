from hashlib import sha1
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
    CellObservation,
    ObservationBlock,
    ObservationType,
    OCIDCell,
    OCIDCellArea,
    Radio,
    Wifi,
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


class CellAreaPositionFactory(BaseFactory):

    radio = Radio.gsm
    mcc = GB_MCC
    mnc = GB_MNC
    lac = fuzzy.FuzzyInteger(100, 999)
    lat = GB_LAT
    lon = GB_LON
    range = LAC_MIN_ACCURACY


class CellPositionFactory(CellAreaPositionFactory):

    cid = fuzzy.FuzzyInteger(1000, 9999)
    psc = fuzzy.FuzzyInteger(100, 500)
    range = CELL_MIN_ACCURACY


class CellFactory(CellPositionFactory):

    class Meta:
        model = Cell.create


class CellAreaFactory(CellAreaPositionFactory):

    class Meta:
        model = CellArea.create


class OCIDCellFactory(CellPositionFactory):

    class Meta:
        model = OCIDCell.create


class OCIDCellAreaFactory(CellAreaPositionFactory):

    class Meta:
        model = OCIDCellArea.create


class CellObservationFactory(CellPositionFactory):

    class Meta:
        model = CellObservation.create


class ObservationBlockFactory(BaseFactory):

    class Meta:
        model = ObservationBlock

    measure_type = ObservationType.cell
    start_id = 10
    end_id = 20
    s3_key = '201502/cell_10_200.zip'
    archive_sha = sha1('').digest()
    archive_date = None


class WifiPositionFactory(BaseFactory):

    key = FuzzyWifiKey()
    lat = GB_LAT
    lon = GB_LON
    range = WIFI_MIN_ACCURACY


class WifiFactory(WifiPositionFactory):

    class Meta:
        model = Wifi.create


class WifiObservationFactory(WifiPositionFactory):

    class Meta:
        model = WifiObservation.create
