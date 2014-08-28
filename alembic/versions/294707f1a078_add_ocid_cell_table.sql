-- Running upgrade 5aa7d2b976eb -> 294707f1a078

CREATE TABLE `ocid_cell` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `radio` tinyint(4) DEFAULT NULL,
  `mcc` smallint(6) DEFAULT NULL,
  `mnc` smallint(6) DEFAULT NULL,
  `lac` int(11) DEFAULT NULL,
  `cid` int(11) DEFAULT NULL,
  `psc` smallint(6) DEFAULT NULL,
  `range` int(11) DEFAULT NULL,
  `total_measures` int(10) unsigned DEFAULT NULL,
  `changeable` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ocid_cell_idx_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `ocid_cell_created_idx` (`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

UPDATE alembic_version SET version_num='294707f1a078';

