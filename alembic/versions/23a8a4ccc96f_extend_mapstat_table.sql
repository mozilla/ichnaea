-- Running upgrade 45059acb751f -> 23a8a4ccc96f

RENAME table mapstat to mapstat_old;

CREATE TABLE `mapstat` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `time` date DEFAULT NULL,
  `lat` int(11) DEFAULT NULL,
  `lon` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `mapstat_lat_lon_unique` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO mapstat (time, lat, lon)
(SELECT date(now()) as today, lat, lon FROM mapstat_old);

DROP TABLE mapstat_old;

UPDATE alembic_version SET version_num='23a8a4ccc96f';
