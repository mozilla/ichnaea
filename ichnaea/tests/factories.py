from hashlib import sha1

import factory
from factory.alchemy import SQLAlchemyModelFactory

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
    SESSION,
)


class BaseFactory(SQLAlchemyModelFactory):

    class Meta:
        strategy = factory.CREATE_STRATEGY

    @classmethod
    def _create(cls, constructor, _session=None, *args, **kwargs):
        """Create an instance of the model, and save it to the database."""
        obj = constructor(*args, **kwargs)
        if _session is None:
            _session = SESSION['default']
        _session.add(obj)
        return obj

    @classmethod
    def _setup_next_sequence(cls):
        # BBB: Override back to BaseFactory implementation, this backports
        # a fix from factory-boy 2.5.0,
        # refs https://github.com/rbarrois/factory_boy/issues/78
        return 0


class CellAreaPositionFactory(BaseFactory):

    radio = Radio.gsm
    mcc = GB_MCC
    mnc = 10
    lac = 10
    lat = GB_LAT
    lon = GB_LON
    range = 35000


class CellPositionFactory(CellAreaPositionFactory):

    cid = 10
    range = 2000


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

    key = '101010101010'
    lat = GB_LAT
    lon = GB_LON


class WifiFactory(WifiPositionFactory):

    class Meta:
        model = Wifi.create


class WifiObservationFactory(WifiPositionFactory):

    class Meta:
        model = WifiObservation.create
