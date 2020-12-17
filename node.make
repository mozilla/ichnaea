HERE = $(shell pwd)
STATIC_ROOT = $(HERE)/ichnaea/content/static
CSS_ROOT = $(STATIC_ROOT)/css
FONT_ROOT = $(STATIC_ROOT)/fonts
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
cleancss -o $@ $^
endef

define run-uglifyjs =
uglifyjs $^ -c -o $@
endef

.PHONY: all
all: css js

.PHONY: clean
clean: cleancss cleanjs cleanfonts
	rm -f $(HERE)/docker/node/npm-shrinkwrap.json

.PHONY: shrinkwrap
shrinkwrap: $(HERE)/docker/node/npm-shrinkwrap.json

$(HERE)/docker/node/npm-shrinkwrap.json: $(NODE_ROOT)/npm-shrinkwrap.json ; $(copy-file)

.PHONY: css
css: shrinkwrap
css: $(CSS_ROOT)/bundle-base.css
css: $(CSS_ROOT)/bundle-map.css
css: $(CSS_ROOT)/bundle-stat-regions.css
css: $(CSS_ROOT)/images/icons.svg
css: $(FONT_ROOT)/FontAwesome.otf

.PHONY: cleancss
cleancss:
	rm -f \
		$(CSS_ROOT)/bundle-base.css \
		$(CSS_ROOT)/bundle-map.css \
		$(CSS_ROOT)/bundle-stat-regions.css \
		$(CSS_ROOT)/font-awesome.css \
		$(CSS_ROOT)/jquery.dataTables.css \
		$(CSS_ROOT)/mapbox.uncompressed.css \
		$(CSS_ROOT)/images/*

.PHONY: cleanfonts
cleanfonts:
	rm -f \
		$(FONT_ROOT)/FontAwesome.otf \
		$(FONT_ROOT)/fontawesome-webfont.*

$(CSS_ROOT)/bundle-base.css: $(CSS_ROOT)/base.css ; $(run-cleancss)
$(CSS_ROOT)/bundle-map.css: $(CSS_ROOT)/font-awesome.css $(CSS_ROOT)/mapbox.uncompressed.css ; $(run-cleancss)
$(CSS_ROOT)/bundle-stat-regions.css: $(CSS_ROOT)/jquery.dataTables.css ; $(run-cleancss)

$(CSS_ROOT)/font-awesome.css: $(NODE_MODULES)/font-awesome/css/font-awesome.css ; $(copy-file)
$(CSS_ROOT)/jquery.dataTables.css: $(NODE_MODULES)/datatables/media/css/jquery.dataTables.css ; $(copy-file)
$(CSS_ROOT)/mapbox.uncompressed.css: $(NODE_MODULES)/mapbox.js/dist/mapbox.uncompressed.css ; $(copy-file)

# Copy all images, using icons.svg as a placeholder to get directories
$(CSS_ROOT)/images/icons.svg: $(NODE_MODULES)/mapbox.js/dist/images/icons.svg
	cp $(<D)/*.png $(<D)/*.svg $(@D)/

# Copy all fonts, using FontAwesome.otf to get directories
$(FONT_ROOT)/FontAwesome.otf: $(NODE_MODULES)/font-awesome/fonts/FontAwesome.otf
	$(copy-file)
	cp $(<D)/fontawesome-webfont.* $(@D)/

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
		$(JS_ROOT)/L.Control.Locate.js \
		$(JS_ROOT)/bundle-base.js \
		$(JS_ROOT)/bundle-map.js \
		$(JS_ROOT)/bundle-privacy.js \
		$(JS_ROOT)/bundle-stat-regions.js \
		$(JS_ROOT)/bundle-stat.js \
		$(JS_ROOT)/jquery.dataTables.js \
		$(JS_ROOT)/jquery.flot.js \
		$(JS_ROOT)/jquery.flot.time.js \
		$(JS_ROOT)/jquery.js \
		$(JS_ROOT)/leaflet-hash.js \
		$(JS_ROOT)/mapbox.uncompressed.js

$(JS_ROOT)/bundle-base.js: $(JS_ROOT)/jquery.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-map.js: $(JS_ROOT)/mapbox.uncompressed.js $(JS_ROOT)/leaflet-hash.js $(JS_ROOT)/L.Control.Locate.js $(JS_ROOT)/map.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-privacy.js: $(JS_ROOT)/privacy.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-stat-regions.js: $(JS_ROOT)/jquery.dataTables.js $(JS_ROOT)/stat-regions.js ; $(run-uglifyjs)
$(JS_ROOT)/bundle-stat.js: $(JS_ROOT)/jquery.flot.js $(JS_ROOT)/jquery.flot.time.js $(JS_ROOT)/stat.js ; $(run-uglifyjs)

$(JS_ROOT)/L.Control.Locate.js: $(NODE_MODULES)/leaflet.locatecontrol/src/L.Control.Locate.js ; $(copy-file)
$(JS_ROOT)/jquery.dataTables.js: $(NODE_MODULES)/datatables/media/js/jquery.dataTables.js ; $(copy-file)
$(JS_ROOT)/jquery.flot.js: $(NODE_MODULES)/jquery-flot/jquery.flot.js ; $(copy-file)
$(JS_ROOT)/jquery.flot.time.js: $(NODE_MODULES)/jquery-flot/jquery.flot.time.js ; $(copy-file)
$(JS_ROOT)/jquery.js: $(NODE_MODULES)/jquery/dist/jquery.js ; $(copy-file)
$(JS_ROOT)/leaflet-hash.js: $(NODE_MODULES)/leaflet-hash/leaflet-hash.js ; $(copy-file)
$(JS_ROOT)/mapbox.uncompressed.js: $(NODE_MODULES)/mapbox.js/dist/mapbox.uncompressed.js ; $(copy-file)
