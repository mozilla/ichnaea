import math

import colander


class BoundedFloat(colander.Float):
    """
    A type representing a float, which does not allow
    +/-nan and +/-inf but returns `colander.null` instead.
    """

    def deserialize(self, schema, cstruct):
        value = super(BoundedFloat, self).deserialize(schema, cstruct)
        if value is colander.null or math.isnan(value) or math.isinf(value):
            return colander.null
        return value
