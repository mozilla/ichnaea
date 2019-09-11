"""
Colander schemata describing the public v1/submit HTTP API.
"""

import colander

from ichnaea.api.schema import (
    OptionalBoundedFloatNode,
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
    OptionalStringNode,
    OptionalStringVocabularyNode,
    UnixTimeFromString,
)

RADIO_STRINGS = ["gsm", "cdma", "umts", "wcdma", "lte"]
SOURCE_STRINGS = ["fixed", "gnss", "fused", "query"]


class BlueV0Schema(OptionalMappingSchema):

    key = OptionalStringNode(to_name="macAddress")

    age = OptionalIntNode()
    name = OptionalStringNode()
    signal = OptionalIntNode(to_name="signalStrength")

    def deserialize(self, data):
        data = super(BlueV0Schema, self).deserialize(data)
        if "macAddress" not in data:
            return colander.drop
        return data


class CellV0Schema(OptionalMappingSchema):

    radio = OptionalStringVocabularyNode(vocabulary=RADIO_STRINGS, to_name="radioType")
    mcc = OptionalIntNode(to_name="mobileCountryCode")
    mnc = OptionalIntNode(to_name="mobileNetworkCode")
    lac = OptionalIntNode(to_name="locationAreaCode")
    cid = OptionalIntNode(to_name="cellId")

    age = OptionalIntNode()
    asu = OptionalIntNode()
    psc = OptionalIntNode(to_name="primaryScramblingCode")
    serving = OptionalIntNode()
    signal = OptionalIntNode(to_name="signalStrength")
    ta = OptionalIntNode(to_name="timingAdvance")


class WifiV0Schema(OptionalMappingSchema):

    key = OptionalStringNode(to_name="macAddress")

    age = OptionalIntNode()
    channel = OptionalIntNode()
    frequency = OptionalIntNode()
    radio = OptionalStringNode(to_name="radioType")
    signal = OptionalIntNode(to_name="signalStrength")
    signalToNoiseRatio = OptionalIntNode()
    ssid = OptionalStringNode()

    def deserialize(self, data):
        data = super(WifiV0Schema, self).deserialize(data)
        if "macAddress" not in data:
            return colander.drop
        return data


class BaseReportV0Schema(OptionalMappingSchema):

    lat = OptionalBoundedFloatNode(to_name="latitude")
    lon = OptionalBoundedFloatNode(to_name="longitude")

    time = OptionalNode(UnixTimeFromString(), to_name="timestamp")
    accuracy = OptionalBoundedFloatNode()
    age = OptionalIntNode()
    altitude = OptionalBoundedFloatNode()
    altitude_accuracy = OptionalBoundedFloatNode(to_name="altitudeAccuracy")
    heading = OptionalBoundedFloatNode()
    pressure = OptionalBoundedFloatNode()
    radio = OptionalStringVocabularyNode(vocabulary=RADIO_STRINGS, to_name="radioType")
    speed = OptionalBoundedFloatNode()
    source = OptionalStringVocabularyNode(
        vocabulary=SOURCE_STRINGS, validator=colander.OneOf(SOURCE_STRINGS)
    )


class ReportV0Schema(BaseReportV0Schema):

    _position_fields = (
        "latitude",
        "longitude",
        "accuracy",
        "altitude",
        "altitudeAccuracy",
        "age",
        "heading",
        "pressure",
        "speed",
        "source",
    )

    @colander.instantiate(to_name="bluetoothBeacons", missing=())
    class blue(OptionalSequenceSchema):
        sequence_item = BlueV0Schema()

    @colander.instantiate(to_name="cellTowers", missing=())
    class cell(OptionalSequenceSchema):
        sequence_item = CellV0Schema()

    @colander.instantiate(to_name="wifiAccessPoints", missing=())
    class wifi(OptionalSequenceSchema):
        sequence_item = WifiV0Schema()

    def deserialize(self, data):
        data = super(ReportV0Schema, self).deserialize(data)
        if data is colander.drop or data is colander.null:  # pragma: no cover
            return colander.drop

        if not (
            data.get("bluetoothBeacons")
            or data.get("cellTowers")
            or data.get("wifiAccessPoints")
        ):
            return colander.drop

        top_radio = data.get("radioType", None)
        for cell in data.get("cellTowers", ()):
            if top_radio and ("radioType" not in cell or not cell["radioType"]):
                cell["radioType"] = top_radio
            if cell.get("radioType") == "umts":
                cell["radioType"] = "wcdma"

        if "radioType" in data:
            del data["radioType"]

        position_data = {}
        for field in self._position_fields:
            if field in data:
                position_data[field] = data[field]
                del data[field]
        if position_data:
            data["position"] = position_data

        return data


class SubmitV0Schema(OptionalMappingSchema):
    @colander.instantiate()
    class items(OptionalSequenceSchema):

        report = ReportV0Schema()


SUBMIT_V0_SCHEMA = SubmitV0Schema()
