from colander import Invalid
from ichnaea.data.schema import (
    ValidCellKeySchema,
    ValidWifiKeySchema,
)


def normalized_wifi_dict(data):
    """
    Returns a normalized copy of the provided wifi dict data,
    or None if the dict was invalid.
    """
    try:
        validated = ValidWifiKeySchema().deserialize(data)
    except Invalid:
        validated = None
    return validated


def normalized_cell_dict(data, default_radio=-1):
    """
    Returns a normalized copy of the provided cell dict data,
    or None if the dict was invalid.
    """
    try:
        validated = ValidCellKeySchema().deserialize(
            data, default_radio=default_radio)
    except Invalid:
        validated = None
    return validated
