$(document).ready(function() {
    var map = L.mapbox.map('map', 'mozilla-webprod.map-05ad0a21', {
        minZoom: 2,
        maxZoom: 15
    }).setView([0, 10], 2);

    // add open street map attribution for base tiles
    map.infoControl.addInfo(
        '© <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    );

    // add tile layer
    L.tileLayer('/tiles/{z}/{x}/{y}.png', {
    }).addTo(map);

    // add tile layer
    L.mapbox.tileLayer('mozilla-webprod.map-5e1cee8a', {
        detectRetina: true
    }).addTo(map);

});
