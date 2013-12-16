$(document).ready(function() {
    var map = L.mapbox.map('map', 'mozilla-webprod.g7ilhcl5', {
        maxZoom: 13,
        tileLayer: { detectRetina: true }
    }).setView([0, 10], 2);

    // add open street map attribution for base tiles
    map.infoControl.addInfo(
        '© <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    );

    // add tile layer
    L.tileLayer('//tiles/{z}/{x}/{y}.png', {
        opacity: 0.8
    }).addTo(map);

});
