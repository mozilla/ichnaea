-- Running upgrade 1ac6c3d2ccc4 -> 2f26a4df27af

ALTER TABLE cell CHANGE COLUMN lat lat_int INTEGER(11), ADD COLUMN lat DOUBLE AFTER lat_int, CHANGE COLUMN max_lat max_lat_int INTEGER(11), ADD COLUMN max_lat DOUBLE AFTER max_lat_int, CHANGE COLUMN min_lat min_lat_int INTEGER(11), ADD COLUMN min_lat DOUBLE AFTER min_lat_int, CHANGE COLUMN lon lon_int INTEGER(11), ADD COLUMN lon DOUBLE AFTER lon_int, CHANGE COLUMN max_lon max_lon_int INTEGER(11), ADD COLUMN max_lon DOUBLE AFTER max_lon_int, CHANGE COLUMN min_lon min_lon_int INTEGER(11), ADD COLUMN min_lon DOUBLE AFTER min_lon_int;

UPDATE cell SET lat = lat_int * 0.0000001, max_lat = max_lat_int * 0.0000001, min_lat = min_lat_int * 0.0000001, lon = lon_int * 0.0000001, max_lon = max_lon_int * 0.0000001, min_lon = min_lon_int * 0.0000001;

ALTER TABLE cell DROP COLUMN lat_int, DROP COLUMN max_lat_int, DROP COLUMN min_lat_int, DROP COLUMN lon_int, DROP COLUMN max_lon_int, DROP COLUMN min_lon_int;

OPTIMIZE TABLE cell;

ALTER TABLE wifi CHANGE COLUMN lat lat_int INTEGER(11), ADD COLUMN lat DOUBLE AFTER lat_int, CHANGE COLUMN max_lat max_lat_int INTEGER(11), ADD COLUMN max_lat DOUBLE AFTER max_lat_int, CHANGE COLUMN min_lat min_lat_int INTEGER(11), ADD COLUMN min_lat DOUBLE AFTER min_lat_int, CHANGE COLUMN lon lon_int INTEGER(11), ADD COLUMN lon DOUBLE AFTER lon_int, CHANGE COLUMN max_lon max_lon_int INTEGER(11), ADD COLUMN max_lon DOUBLE AFTER max_lon_int, CHANGE COLUMN min_lon min_lon_int INTEGER(11), ADD COLUMN min_lon DOUBLE AFTER min_lon_int;

UPDATE wifi SET lat = lat_int * 0.0000001, max_lat = max_lat_int * 0.0000001, min_lat = min_lat_int * 0.0000001, lon = lon_int * 0.0000001, max_lon = max_lon_int * 0.0000001, min_lon = min_lon_int * 0.0000001;

ALTER TABLE wifi DROP COLUMN lat_int, DROP COLUMN max_lat_int, DROP COLUMN min_lat_int, DROP COLUMN lon_int, DROP COLUMN max_lon_int, DROP COLUMN min_lon_int;

OPTIMIZE TABLE wifi;

ALTER TABLE cell_measure CHANGE COLUMN lat lat_int INTEGER(11), ADD COLUMN lat DOUBLE AFTER lat_int, CHANGE COLUMN lon lon_int INTEGER(11), ADD COLUMN lon DOUBLE AFTER lon_int;

UPDATE cell_measure SET lat = lat_int * 0.0000001, lon = lon_int * 0.0000001;

ALTER TABLE cell_measure DROP COLUMN lat_int, DROP COLUMN lon_int;

OPTIMIZE TABLE cell_measure;

ALTER TABLE wifi_measure CHANGE COLUMN lat lat_int INTEGER(11), ADD COLUMN lat DOUBLE AFTER lat_int, CHANGE COLUMN lon lon_int INTEGER(11), ADD COLUMN lon DOUBLE AFTER lon_int;

UPDATE wifi_measure SET lat = lat_int * 0.0000001, lon = lon_int * 0.0000001;

ALTER TABLE wifi_measure DROP COLUMN lat_int, DROP COLUMN lon_int;

OPTIMIZE TABLE wifi_measure;

UPDATE alembic_version SET version_num='2f26a4df27af';

