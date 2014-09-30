$(document).ready(function() {
    // the retina version uses zoom level + 1 image tiles
    // and we only generated tiles down to zoom level 13,
    // noted via the maxNativeZoom restriction on the tile layer
    // we still allow more zoom levels on the base map, to make
    // it easier to see which streets are covered
    var maxZoom = 16;
    if (L.Browser.retina) {
        maxZoom = 15;
    }

    // Restrict to typical Web Mercator bounds
    var southWest = L.latLng(-85.0511, -270.0),
        northEast = L.latLng(85.0511, 270.0),
        bounds = L.latLngBounds(southWest, northEast);

    var map = L.mapbox.map('map', 'mozilla-webprod.map-05ad0a21', {
        minZoom: 1,
        maxZoom: maxZoom,
        maxBounds: bounds,
        tileLayer: { detectRetina: true }
    }).setView([15.0, 10.0], 2);

    var hash = new L.Hash(map);

    // add open street map attribution for base tiles
    map.attributionControl.setPrefix(
        '© <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    );

    // add scale
    L.control.scale({
        'updateWhenIdle': true,
        'imperial': false,
        'maxWidth': 200
    }).addTo(map);

    // add location control
    L.control.locate({
        follow: false,
        locateOptions: {
            enableHighAccuracy: true,
            maximumAge: 3600000,
            maxZoom: 12,
            watch: false
        }
    }).addTo(map);

    // add tile layer
    var tiles = $('#map').data('tiles');
    L.tileLayer(tiles, {
        detectRetina: true,
        maxNativeZoom: 13
    }).addTo(map);

    // add tile layer
    L.mapbox.tileLayer('mozilla-webprod.map-5e1cee8a', {
        detectRetina: true
    }).addTo(map);

});
