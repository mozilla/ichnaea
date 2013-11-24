$(document).ready(function() {
    var map = L.mapbox.map('map', 'mozilla-webprod.g7ilhcl5', {
        maxZoom: 8,
        tileLayer: { detectRetina: true }
    }).setView([0, 10], 2);
    var markers = new L.MarkerClusterGroup({
        spiderfyOnMaxZoom: false,
        removeOutsideVisibleBounds: true,
        maxClusterRadius: 50
    });

    $.ajax({
        url: '/map_world.csv',
        dataType: 'text',
        success: function csvLoad(csv) {
            var geoJson = csv2geojson.csv2geojson(csv, function(err, data) {
                markers.addLayer(L.geoJson(data));
                map.addLayer(markers);
            });
        }
    });
});
