HERE = $(shell pwd)
STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
FONT_ROOT = $(STATIC_ROOT)/fonts
IMG_ROOT = $(STATIC_ROOT)/images
JS_ROOT = $(STATIC_ROOT)/js
NODE_ROOT = /node
NODE_MODULES = $(NODE_ROOT)/node_modules

CLEANCSS = cleancss -d
UGLIFYJS = uglifyjs -c --stats

.PHONY: all js css shrinkwrap

all: css js

shrinkwrap:
	cp $(NODE_ROOT)/npm-shrinkwrap.json $(HERE)/docker/node/

css: shrinkwrap
	$(CLEANCSS) \
		-o $(CSS_ROOT)/bundle-base.css \
		$(CSS_ROOT)/base.css

	cp $(NODE_MODULES)/datatables/media/css/jquery.dataTables.css \
		$(CSS_ROOT)/jquery.dataTables.css
	$(CLEANCSS) -o $(CSS_ROOT)/bundle-stat-regions.css \
		$(CSS_ROOT)/jquery.dataTables.css
		
	cp $(NODE_MODULES)/font-awesome/css/font-awesome.css \
		$(CSS_ROOT)/font-awesome.css
	cp $(NODE_MODULES)/mapbox.js/dist/mapbox.uncompressed.css \
		$(CSS_ROOT)/mapbox.uncompressed.css
	$(CLEANCSS) -o $(CSS_ROOT)/bundle-map.css \
		$(CSS_ROOT)/font-awesome.css \
		$(CSS_ROOT)/mapbox.uncompressed.css

	mkdir -p $(CSS_ROOT)/images/
	cp $(NODE_MODULES)/mapbox.js/dist/images/*.png $(CSS_ROOT)/images/
	cp $(NODE_MODULES)/mapbox.js/dist/images/*.svg $(CSS_ROOT)/images/
	cp $(NODE_MODULES)/mapbox.js/dist/images/images/* $(CSS_ROOT)/images/
	cp $(NODE_MODULES)/font-awesome/fonts/* $(FONT_ROOT)/

js: shrinkwrap
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-privacy.js \
		$(JS_ROOT)/privacy.js

	cp $(NODE_MODULES)/jquery/dist/jquery.js $(JS_ROOT)/jquery.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-base.js \
		$(JS_ROOT)/ga.js \
		$(JS_ROOT)/jquery.js

	cp $(NODE_MODULES)/datatables/media/js/jquery.dataTables.js \
		$(JS_ROOT)/jquery.dataTables.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-stat-regions.js \
		$(JS_ROOT)/jquery.dataTables.js \
		$(JS_ROOT)/stat-regions.js

	cp $(NODE_MODULES)/jquery-flot/jquery.flot.js \
		$(JS_ROOT)/jquery.flot.js
	cp $(NODE_MODULES)/jquery-flot/jquery.flot.time.js \
		$(JS_ROOT)/jquery.flot.time.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-stat.js \
		$(JS_ROOT)/jquery.flot.js \
		$(JS_ROOT)/jquery.flot.time.js \
		$(JS_ROOT)/stat.js

	cp $(NODE_MODULES)/mapbox.js/dist/mapbox.uncompressed.js \
		$(JS_ROOT)/mapbox.uncompressed.js
	cp $(NODE_MODULES)/leaflet-hash/leaflet-hash.js \
		$(JS_ROOT)/leaflet-hash.js
	cp $(NODE_MODULES)/leaflet.locatecontrol/src/L.Control.Locate.js \
		$(JS_ROOT)/L.Control.Locate.js
	$(UGLIFYJS) -o $(JS_ROOT)/bundle-map.js \
		$(JS_ROOT)/mapbox.uncompressed.js \
		$(JS_ROOT)/leaflet-hash.js \
		$(JS_ROOT)/L.Control.Locate.js \
		$(JS_ROOT)/map.js
