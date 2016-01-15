/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `api_key` (
  `valid_key` varchar(40) NOT NULL,
  `maxreq` int(11) DEFAULT NULL,
  `log` tinyint(1) DEFAULT NULL,
  `allow_fallback` tinyint(1) DEFAULT NULL,
  `shortname` varchar(40) DEFAULT NULL,
  PRIMARY KEY (`valid_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cell` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `cid` int(10) unsigned NOT NULL,
  `psc` smallint(6) DEFAULT NULL,
  `range` int(11) DEFAULT NULL,
  `total_measures` int(10) unsigned DEFAULT NULL,
  `new_measures` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_created_idx` (`created`),
  KEY `cell_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cell_area` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `range` int(11) DEFAULT NULL,
  `avg_cell_range` int(11) DEFAULT NULL,
  `num_cells` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`radio`,`mcc`,`mnc`,`lac`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cell_blacklist` (
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `cid` int(10) unsigned NOT NULL,
  `time` datetime DEFAULT NULL,
  `count` int(11) DEFAULT NULL,
  PRIMARY KEY (`radio`,`mcc`,`mnc`,`lac`,`cid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `mapstat` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `time` date DEFAULT NULL,
  `lat` int(11) DEFAULT NULL,
  `lon` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `mapstat_lat_lon_unique` (`lat`,`lon`),
  KEY `idx_mapstat_time` (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ocid_cell` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `cid` int(10) unsigned NOT NULL,
  `psc` smallint(6) DEFAULT NULL,
  `range` int(11) DEFAULT NULL,
  `total_measures` int(10) unsigned DEFAULT NULL,
  `changeable` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `ocid_cell_created_idx` (`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ocid_cell_area` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `radio` tinyint(4) NOT NULL,
  `mcc` smallint(6) NOT NULL,
  `mnc` smallint(6) NOT NULL,
  `lac` smallint(5) unsigned NOT NULL,
  `range` int(11) DEFAULT NULL,
  `avg_cell_range` int(11) DEFAULT NULL,
  `num_cells` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`radio`,`mcc`,`mnc`,`lac`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `score` (
  `userid` int(10) unsigned NOT NULL,
  `key` tinyint(4) NOT NULL,
  `time` date NOT NULL,
  `value` int(11) DEFAULT NULL,
  PRIMARY KEY (`key`,`userid`,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `stat` (
  `key` tinyint(4) NOT NULL,
  `time` date NOT NULL,
  `value` bigint(20) unsigned DEFAULT NULL,
  PRIMARY KEY (`key`,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nickname` varchar(128) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_nickname_unique` (`nickname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_0` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_0_country_idx` (`country`),
  KEY `wifi_shard_0_created_idx` (`created`),
  KEY `wifi_shard_0_modified_idx` (`modified`),
  KEY `wifi_shard_0_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_1` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_1_country_idx` (`country`),
  KEY `wifi_shard_1_created_idx` (`created`),
  KEY `wifi_shard_1_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_1_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_2` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_2_country_idx` (`country`),
  KEY `wifi_shard_2_created_idx` (`created`),
  KEY `wifi_shard_2_modified_idx` (`modified`),
  KEY `wifi_shard_2_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_3` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_3_country_idx` (`country`),
  KEY `wifi_shard_3_created_idx` (`created`),
  KEY `wifi_shard_3_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_3_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_4` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_4_country_idx` (`country`),
  KEY `wifi_shard_4_created_idx` (`created`),
  KEY `wifi_shard_4_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_4_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_5` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_5_country_idx` (`country`),
  KEY `wifi_shard_5_created_idx` (`created`),
  KEY `wifi_shard_5_modified_idx` (`modified`),
  KEY `wifi_shard_5_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_6` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_6_country_idx` (`country`),
  KEY `wifi_shard_6_created_idx` (`created`),
  KEY `wifi_shard_6_modified_idx` (`modified`),
  KEY `wifi_shard_6_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_7` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_7_country_idx` (`country`),
  KEY `wifi_shard_7_created_idx` (`created`),
  KEY `wifi_shard_7_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_7_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_8` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_8_country_idx` (`country`),
  KEY `wifi_shard_8_created_idx` (`created`),
  KEY `wifi_shard_8_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_8_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_9` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_9_country_idx` (`country`),
  KEY `wifi_shard_9_created_idx` (`created`),
  KEY `wifi_shard_9_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_9_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_a` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_a_country_idx` (`country`),
  KEY `wifi_shard_a_created_idx` (`created`),
  KEY `wifi_shard_a_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_a_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_b` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_b_country_idx` (`country`),
  KEY `wifi_shard_b_created_idx` (`created`),
  KEY `wifi_shard_b_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_b_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_c` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_c_country_idx` (`country`),
  KEY `wifi_shard_c_created_idx` (`created`),
  KEY `wifi_shard_c_latlon_idx` (`lat`,`lon`),
  KEY `wifi_shard_c_modified_idx` (`modified`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_d` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_d_country_idx` (`country`),
  KEY `wifi_shard_d_created_idx` (`created`),
  KEY `wifi_shard_d_modified_idx` (`modified`),
  KEY `wifi_shard_d_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_e` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_e_country_idx` (`country`),
  KEY `wifi_shard_e_created_idx` (`created`),
  KEY `wifi_shard_e_modified_idx` (`modified`),
  KEY `wifi_shard_e_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_shard_f` (
  `created` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `mac` binary(6) NOT NULL,
  `radius` int(10) unsigned DEFAULT NULL,
  `country` varchar(2) DEFAULT NULL,
  `samples` int(10) unsigned DEFAULT NULL,
  `source` tinyint(4) DEFAULT NULL,
  `block_first` date DEFAULT NULL,
  `block_last` date DEFAULT NULL,
  `block_count` tinyint(3) unsigned DEFAULT NULL,
  PRIMARY KEY (`mac`),
  KEY `wifi_shard_f_country_idx` (`country`),
  KEY `wifi_shard_f_created_idx` (`created`),
  KEY `wifi_shard_f_modified_idx` (`modified`),
  KEY `wifi_shard_f_latlon_idx` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
