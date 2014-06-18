key **(required)**
    The client must check the WiFi SSID for a `_nomap`
    suffix. WiFi networks with such a suffix must not be submitted to the
    server. WiFi networks with a hidden SSID should not be submitted to the
    server either.

    The `key` is the BSSID of the WiFi network. So for example
    a valid key would look similar to `01:23:45:67:89:ab`.

frequency
    The frequency in MHz of the channel over which the client is
    communicating with the access point.

channel
    The channel is a number specified by the IEEE which represents a
    small band of frequencies.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -51 to -113.

signalToNoiseRatio
    The current signal to noise ratio measured in dB.

An example of a valid WiFi record is below:

.. code-block:: javascript

    {
        "key": "01:23:45:67:89:ab",
        "channel": 11,
        "frequency": 2412,
        "signal": -51,
        "signalToNoiseRatio": 37
    }
