import colander
import pytest

from ichnaea.api.transfer.schema import TRANSFER_V1_SCHEMA


class TestSchema(object):

    def test_empty(self):
        with pytest.raises(colander.Invalid):
            TRANSFER_V1_SCHEMA.deserialize({})

    def test_minimal(self):
        data = TRANSFER_V1_SCHEMA.deserialize(
            {'items': []})
        assert 'items' in data
        assert len(data['items']) == 0
