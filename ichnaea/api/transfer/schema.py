import colander

from ichnaea.api.schema import (
    OptionalMappingSchema,
    OptionalSequenceSchema,
)


class ItemV1Schema(OptionalMappingSchema):

    def deserialize(self, data):
        data = super(ItemV1Schema, self).deserialize(data)
        if (data is colander.drop or
                data is colander.null):  # pragma: no cover
            return colander.drop

        if not data:
            return colander.drop

        # TODO
        return data  # pragma: no cover


class TransferV1Schema(OptionalMappingSchema):

    @colander.instantiate()
    class items(OptionalSequenceSchema):  # NOQA
        item = ItemV1Schema()

TRANSFER_V1_SCHEMA = TransferV1Schema()
