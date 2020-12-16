$(document).ready(function() {
    var mapDOMElement = $('#map');
    var mapTilesUrl = mapDOMElement.data('map_tiles_url');
    var mapToken = mapDOMElement.data('map_token');

    // Set public access token
    mapboxgl.accessToken = mapToken

    var map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/dark-v10',
        center: [9.0, 35.0],
        hash: true,
        maxZoom: 12,
        maxBounds: [[-210, -85.0511], [210, 85.0511]],
    });

    map.on('load', function() {

      map.addControl(new mapboxgl.NavigationControl(), 'top-left');
      map.addControl(new mapboxgl.GeolocateControl(), 'top-left');
      map.addControl(new mapboxgl.ScaleControl(), 'bottom-left');
      map.addControl(
        new MapboxGeocoder({
          accessToken: mapToken,
          mapboxgl: mapboxgl,
          zoom: 10,
          collapsed: true,
          types: 'country,region,postcode,place,locality'
        }),
        'top-left'
      );

      if (mapTilesUrl) {
        // Add contribution tiles source
        map.addSource('contributions', {
          type: 'raster',
          tiles: [mapTilesUrl],
          maxzoom: 11,
          tileSize: 256
        });
        map.addLayer({
          id: 'contributions-layer',
          source: 'contributions',
          type: 'raster'
        });
      }
    });

});
