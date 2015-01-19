from colander import Invalid
from ichnaea.data.schema import (
    ValidCellMeasureSchema,
    ValidCellSchema,
    ValidMeasureSchema,
    ValidWifiSchema,
)


def normalized_measure_dict(data):
    try:
        validated = ValidMeasureSchema().deserialize(data)
    except Invalid:
        validated = None
    return validated


def normalized_wifi_dict(data):
    """
    Returns a normalized copy of the provided wifi dict data,
    or None if the dict was invalid.
    """
    try:
        validated = ValidWifiSchema().deserialize(data)
    except Invalid:
        validated = None
    return validated


def normalized_cell_dict(data, default_radio=-1):
    """
    Returns a normalized copy of the provided cell dict data,
    or None if the dict was invalid.
    """
    try:
        validated = ValidCellSchema().deserialize(
            data, default_radio=default_radio)
    except Invalid:
        validated = None
    return validated


def normalized_cell_measure_dict(data, measure_radio=-1):
    """
    Returns a normalized copy of the provided cell-measure dict data,
    or None if the dict was invalid.
    """
    try:
        validated = ValidCellMeasureSchema().deserialize(data)
    except Invalid:
        validated = None
    return validated
