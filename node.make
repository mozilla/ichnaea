HERE = $(shell pwd)
STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
FONT_ROOT = $(STATIC_ROOT)/fonts
IMG_ROOT = $(STATIC_ROOT)/images
JS_ROOT = $(STATIC_ROOT)/js
BOWER_COMPONENTS = /node/bower_components

CLEANCSS = cleancss -d
UGLIFYJS = uglifyjs -c --stats

.PHONY: all js css

all: css js

css:
	cp $(BOWER_COMPONENTS)/mozilla-tabzilla/css/tabzilla.css \
		$(CSS_ROOT)/tabzilla.css

	mkdir -p $(STATIC_ROOT)/media/img/
	cp $(BOWER_COMPONENTS)/mozilla-tabzilla/media/img/tabzilla-static.png \
		$(STATIC_ROOT)/media/img/tabzilla-static.png
	cp $(BOWER_COMPONENTS)/mozilla-tabzilla/media/img/tabzilla-static-high-res.png \
		$(STATIC_ROOT)/media/img/tabzilla-static-high-res.png

	$(CLEANCSS) \
		-o $(CSS_ROOT)/bundle-base.css \
		$(CSS_ROOT)/tabzilla.css \
		$(CSS_ROOT)/base.css

	cp $(BOWER_COMPONENTS)/datatables/media/css/jquery.dataTables.css \
		$(CSS_ROOT)/jquery.dataTables.css
	$(CLEANCSS) -o $(CSS_ROOT)/bundle-stat-regions.css \
		$(CSS_ROOT)/jquery.dataTables.css
		
	cp $(BOWER_COMPONENTS)/font-awesome/css/font-awesome.css \
		$(CSS_ROOT)/font-awesome.css
	cp $(BOWER_COMPONENTS)/mapbox.js/mapbox.uncompressed.css \
		$(CSS_ROOT)/mapbox.uncompressed.css
	$(CLEANCSS) -o $(CSS_ROOT)/bundle-map.css \
		$(CSS_ROOT)/font-awesome.css \
		$(CSS_ROOT)/mapbox.uncompressed.css

	mkdir -p $(CSS_ROOT)/images/
	cp $(BOWER_COMPONENTS)/mapbox.js/images/* $(CSS_ROOT)/images/
	rm -f $(CSS_ROOT)/images/render.sh
	cp $(BOWER_COMPONENTS)/font-awesome/fonts/* $(FONT_ROOT)/

js:
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-privacy.js \
		$(JS_ROOT)/privacy.js

	cp $(BOWER_COMPONENTS)/jquery/dist/jquery.js $(JS_ROOT)/jquery.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-base.js \
		$(JS_ROOT)/ga.js \
		$(JS_ROOT)/jquery.js

	cp $(BOWER_COMPONENTS)/datatables/media/js/jquery.dataTables.js \
		$(JS_ROOT)/jquery.dataTables.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-stat-regions.js \
		$(JS_ROOT)/jquery.dataTables.js \
		$(JS_ROOT)/stat-regions.js

	cp $(BOWER_COMPONENTS)/flot/jquery.flot.js \
		$(JS_ROOT)/jquery.flot.js
	cp $(BOWER_COMPONENTS)/flot/jquery.flot.time.js \
		$(JS_ROOT)/jquery.flot.time.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-stat.js \
		$(JS_ROOT)/jquery.flot.js \
		$(JS_ROOT)/jquery.flot.time.js \
		$(JS_ROOT)/stat.js

	cp $(BOWER_COMPONENTS)/mapbox.js/mapbox.uncompressed.js \
		$(JS_ROOT)/mapbox.uncompressed.js
	cp $(BOWER_COMPONENTS)/leaflet-hash/leaflet-hash.js \
		$(JS_ROOT)/leaflet-hash.js
	cp $(BOWER_COMPONENTS)/leaflet.locatecontrol/src/L.Control.Locate.js \
		$(JS_ROOT)/L.Control.Locate.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-map.js \
		$(JS_ROOT)/mapbox.uncompressed.js \
		$(JS_ROOT)/leaflet-hash.js \
		$(JS_ROOT)/L.Control.Locate.js \
		$(JS_ROOT)/map.js
