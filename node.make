HERE = $(shell pwd)
STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
JS_ROOT = $(STATIC_ROOT)/js
NODE_ROOT = /node
NODE_MODULES = $(NODE_ROOT)/node_modules

# Notes from https://www.gnu.org/software/make/manual/html_node/Automatic-Variables.html
# $@ is the target / output filename
# $< is the first prerequisite filenames
# $^ is all the prerequisite filenames
# $(@D) is the directory part of the target
# $(<D) is the directory part of the first prerequisite

define copy-file =
cp $< $@
endef

define run-cleancss =
$(NODE_MODULES)/clean-css-cli/bin/cleancss -o $@ $^
endef

define run-uglifyjs =
$(NODE_MODULES)/uglify-js/bin/uglifyjs $^ -c -o $@
endef

.PHONY: all
all: css js

.PHONY: clean
clean: cleancss cleanjs
	rm -f $(HERE)/docker/node/npm-shrinkwrap.json

.PHONY: shrinkwrap
shrinkwrap: $(HERE)/docker/node/npm-shrinkwrap.json

$(HERE)/docker/node/npm-shrinkwrap.json: $(NODE_ROOT)/npm-shrinkwrap.json ; $(copy-file)

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

$(CSS_ROOT)/bundle-base.css: $(CSS_ROOT)/base.css ; $(run-cleancss)
$(CSS_ROOT)/bundle-map.css: $(CSS_ROOT)/mapbox-gl.css $(CSS_ROOT)/mapbox-gl-geocoder.css ; $(run-cleancss)
$(CSS_ROOT)/bundle-stat-regions.css: $(CSS_ROOT)/jquery.dataTables.css ; $(run-cleancss)

$(CSS_ROOT)/jquery.dataTables.css: $(NODE_MODULES)/datatables/media/css/jquery.dataTables.css ; $(copy-file)
$(CSS_ROOT)/mapbox-gl.css: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl.css ; $(copy-file)
$(CSS_ROOT)/mapbox-gl-geocoder.css: $(NODE_MODULES)/@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.css ; $(copy-file)

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
		$(JS_ROOT)/mapbox-gl-geocoder.min.js \
		$(JS_ROOT)/mapbox-gl-unminified.js \
		$(JS_ROOT)/mapbox-gl-unminified.js.map

$(JS_ROOT)/bundle-base.js: $(JS_ROOT)/jquery.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-map.js: $(JS_ROOT)/mapbox-gl-unminified.js $(JS_ROOT)/mapbox-gl-geocoder.min.js $(JS_ROOT)/map.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-privacy.js: $(JS_ROOT)/privacy.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-stat-regions.js: $(JS_ROOT)/jquery.dataTables.js $(JS_ROOT)/stat-regions.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-stat.js: $(JS_ROOT)/jquery.flot.js $(JS_ROOT)/jquery.flot.time.js $(JS_ROOT)/stat.js ; $(run-uglifyjs)

$(JS_ROOT)/jquery.dataTables.js: $(NODE_MODULES)/datatables/media/js/jquery.dataTables.js ; $(copy-file)
$(JS_ROOT)/jquery.flot.js: $(NODE_MODULES)/jquery-flot/jquery.flot.js ; $(copy-file)
$(JS_ROOT)/jquery.flot.time.js: $(NODE_MODULES)/jquery-flot/jquery.flot.time.js ; $(copy-file)
$(JS_ROOT)/jquery.js: $(NODE_MODULES)/jquery/dist/jquery.js ; $(copy-file)
$(JS_ROOT)/mapbox-gl-geocoder.min.js: $(NODE_MODULES)/@mapbox/mapbox-gl-geocoder/dist/mapbox-gl-geocoder.min.js ; $(copy-file)
$(JS_ROOT)/mapbox-gl-unminified.js.map: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl-unminified.js.map ; $(copy-file)
$(JS_ROOT)/mapbox-gl-unminified.js: $(NODE_MODULES)/mapbox-gl/dist/mapbox-gl-unminified.js ; $(copy-file)
