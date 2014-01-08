$(document).ready(function() {
    var map = L.mapbox.map('map', 'mozilla-webprod.map-05ad0a21', {
        minZoom: 1,
        maxZoom: 15,
        tileLayer: { detectRetina: true }
    }).setView([15, 10], 2);

    // add open street map attribution for base tiles
    map.infoControl.addInfo(
        '© <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    );

    // add tile layer
    L.tileLayer('/tiles/{z}/{x}/{y}.png', {
        detectRetina: true
    }).addTo(map);

    // add tile layer
    L.mapbox.tileLayer('mozilla-webprod.map-5e1cee8a', {
        detectRetina: true
    }).addTo(map);

});
