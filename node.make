HERE = $(shell pwd)
STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
FONT_ROOT = $(STATIC_ROOT)/fonts
IMG_ROOT = $(STATIC_ROOT)/images
JS_ROOT = $(STATIC_ROOT)/js
NODE_ROOT = /node
NODE_MODULES = $(NODE_ROOT)/node_modules

CLEANCSS = cleancss -d
UGLIFYJS = uglifyjs -c --timings

# Notes from https://www.gnu.org/software/make/manual/html_node/Automatic-Variables.html
# $@ is the target / output filename
# $< is the first prerequisite filenames
# $^ is all the prerequisite filenames

.PHONY: all
all: css js

.PHONY: clean
clean: cleancss cleanjs
	rm -f $(HERE)/docker/node/npm-shrinkwrap.json

.PHONY: shrinkwrap
shrinkwrap: $(HERE)/docker/node/npm-shrinkwrap.json

$(HERE)/docker/node/npm-shrinkwrap.json: $(NODE_ROOT)/npm-shrinkwrap.json
	cp $< $@

.PHONY: css
css: shrinkwrap
css: $(CSS_ROOT)/bundle-base.css
css: $(CSS_ROOT)/bundle-map.css
css: $(CSS_ROOT)/bundle-stat-regions.css

.PHONY: cleancss
cleancss:
	rm -f \
		$(CSS_ROOT)/bundle-base.css \
		$(CSS_ROOT)/bundle-map.css \
		$(CSS_ROOT)/bundle-stat-regions.css \
		$(CSS_ROOT)/jquery.dataTables.css \
		$(CSS_ROOT)/mapbox-gl.css \
		$(CSS_ROOT)/mapbox-gl-geocoder.css

$(CSS_ROOT)/bundle-base.css: $(CSS_ROOT)/base.css
	$(CLEANCSS) -o $(CSS_ROOT)/bundle-base.css \
		$(CSS_ROOT)/base.css

$(CSS_ROOT)/jquery.dataTables.css: $(NODE_MODULES)/datatables/media/css/jquery.dataTables.css
	cp $< $@

$(CSS_ROOT)/mapbox-gl.css: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl.css
	cp $< $@

$(CSS_ROOT)/mapbox-gl-geocoder.css: $(NODE_MODULES)/@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.css
	cp $< $@

$(CSS_ROOT)/bundle-stat-regions.css: $(CSS_ROOT)/jquery.dataTables.css
	$(CLEANCSS) -o $@ $^

$(CSS_ROOT)/bundle-map.css: $(CSS_ROOT)/mapbox-gl.css $(CSS_ROOT)/mapbox-gl-geocoder.css
	$(CLEANCSS) -o $@ $^

.PHONY: js
js: shrinkwrap
js: $(JS_ROOT)/bundle-base.js
js: $(JS_ROOT)/bundle-map.js
js: $(JS_ROOT)/bundle-privacy.js
js: $(JS_ROOT)/bundle-stat-regions.js
js: $(JS_ROOT)/bundle-stat.js

.PHONY: cleanjs
cleanjs:
	rm -f \
		$(JS_ROOT)/bundle-base.js \
		$(JS_ROOT)/bundle-map.js \
		$(JS_ROOT)/bundle-privacy.js \
		$(JS_ROOT)/bundle-stat-regions.js \
		$(JS_ROOT)/bundle-stat.js \
		$(JS_ROOT)/jquery.dataTables.js \
		$(JS_ROOT)/jquery.flot.js \
		$(JS_ROOT)/jquery.flot.time.js \
		$(JS_ROOT)/jquery.js \
		$(JS_ROOT)/mapbox-gl.js \
		$(JS_ROOT)/mapbox-gl.js.map \
		$(JS_ROOT)/mapbox-gl-geocoder.min.js \
		$(JS_ROOT)/mapbox-gl-unminified.js \
		$(JS_ROOT)/mapbox-gl-unminified.js.map

$(JS_ROOT)/bundle-privacy.js: $(JS_ROOT)/privacy.js
	$(UGLIFYJS) -o $@ $^

$(JS_ROOT)/jquery.js: $(NODE_MODULES)/jquery/dist/jquery.js
	cp $< $@

$(JS_ROOT)/bundle-base.js: $(JS_ROOT)/jquery.js
	$(UGLIFYJS) -o $@ $^

$(JS_ROOT)/jquery.dataTables.js: $(NODE_MODULES)/datatables/media/js/jquery.dataTables.js
	cp $< $@

$(JS_ROOT)/bundle-stat-regions.js: $(JS_ROOT)/jquery.dataTables.js $(JS_ROOT)/stat-regions.js
	$(UGLIFYJS) -o $@ $^

$(JS_ROOT)/jquery.flot.js: $(NODE_MODULES)/jquery-flot/jquery.flot.js
	cp $< $@

$(JS_ROOT)/jquery.flot.time.js: $(NODE_MODULES)/jquery-flot/jquery.flot.time.js
	cp $< $@

$(JS_ROOT)/bundle-stat.js: $(JS_ROOT)/jquery.flot.js $(JS_ROOT)/jquery.flot.time.js $(JS_ROOT)/stat.js
	$(UGLIFYJS) -o $@ $^

$(JS_ROOT)/mapbox-gl.js: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl.js
	cp $< $@

$(JS_ROOT)/mapbox-gl.js.map: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl.js.map
	cp $< $@

$(JS_ROOT)/mapbox-gl-unminified.js: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl-unminified.js
	cp $< $@

$(JS_ROOT)/mapbox-gl-unminified.js.map: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl-unminified.js.map
	cp $< $@

$(JS_ROOT)/mapbox-gl-geocoder.min.js: $(NODE_MODULES)/@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.min.js
	cp $< $@

# uglifyjs 3.12 is unable to compress mapbox-gl.js 2.0.0
#$(JS_ROOT)/bundle-map.js: $(JS_ROOT)/mapbox-gl.js $(JS_ROOT)/map.js
#	cp $(JS_ROOT)/mapbox-gl.js $(JS_ROOT)/bundle-map.js
#	uglifyjs $(JS_ROOT)/map.js >> $(JS_ROOT)/bundle-map.js

$(JS_ROOT)/bundle-map.js: $(JS_ROOT)/mapbox-gl-unminified.js $(JS_ROOT)/mapbox-gl-geocoder.min.js $(JS_ROOT)/map.js
	$(UGLIFYJS) -o $@ $^



