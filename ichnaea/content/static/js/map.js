$(document).ready(function() {
    // the retina version uses zoom level + 1 image tiles
    // and we only generated tiles down to zoom level 13,
    // noted via the maxNativeZoom restriction on the tile layer
    // we still allow more zoom levels on the base map, to make
    // it easier to see which streets are covered
    var mapDOMElement = $('#map');
    var mapTilesUrl = mapDOMElement.data('map_tiles_url');
    var mapToken = mapDOMElement.data('map_token');

    // Restrict to typical Web Mercator bounds
    var southWest = L.latLng(-85.0511, -210.0),
        northEast = L.latLng(85.0511, 210.0),
        bounds = L.latLngBounds(southWest, northEast);

    // Set public access token
    L.mapbox.accessToken = mapToken

    var map = L.mapbox.map('map', 'mapbox.dark', {
        maxZoom: 12,
        maxBounds: bounds
    }).setView([35.0, 9.0], 2);

    var hash = new L.Hash(map);

    // add scale
    L.control.scale({
        'updateWhenIdle': true,
        'imperial': false,
        'maxWidth': 200
    }).addTo(map);

    // add location control
    L.control.locate({
        setView: 'once',
        showPopup: false,
        locateOptions: {
            enableHighAccuracy: true,
            maximumAge: 3600000,
            maxZoom: 10,
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
            maxNativeZoom: 11
        }).addTo(map);
    }

});
