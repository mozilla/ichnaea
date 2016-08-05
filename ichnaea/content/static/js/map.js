$(document).ready(function() {
    // the retina version uses zoom level + 1 image tiles
    // and we only generated tiles down to zoom level 13,
    // noted via the maxNativeZoom restriction on the tile layer
    // we still allow more zoom levels on the base map, to make
    // it easier to see which streets are covered
    var mapDOMElement = $('#map');
    var mapIdBase = mapDOMElement.data('map_id_base');
    var mapIdLabels = mapDOMElement.data('map_id_labels');
    var mapTilesUrl = mapDOMElement.data('map_tiles_url');
    var mapToken = mapDOMElement.data('map_token');

    var maxZoom = 15;
    if (L.Browser.retina) {
        maxZoom = 14;
    }

    // Restrict to typical Web Mercator bounds
    var southWest = L.latLng(-85.0511, -270.0),
        northEast = L.latLng(85.0511, 270.0),
        bounds = L.latLngBounds(southWest, northEast);

    // Set public access token
    L.mapbox.accessToken = mapToken

    var map = L.mapbox.map('map', mapIdBase, {
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

    // add geocoding control
    L.mapbox.geocoderControl('mapbox.places', {
        'pointZoom': 10,
        'queryOptions': {'types': 'country,region,postcode,place,locality'}
    }).addTo(map);

    // add tile layer
    if (mapTilesUrl) {
        L.tileLayer(mapTilesUrl, {
            detectRetina: true,
            maxNativeZoom: 12
        }).addTo(map);
    }

    // add tile layer
    if (mapIdLabels) {
        L.mapbox.tileLayer(mapIdLabels, {
            detectRetina: true
        }).addTo(map);
    }

});
