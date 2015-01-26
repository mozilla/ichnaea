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
  `shortname` varchar(40) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`valid_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cell` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `radio` smallint(6) DEFAULT NULL,
  `mcc` smallint(6) DEFAULT NULL,
  `mnc` int(11) DEFAULT NULL,
  `lac` int(11) DEFAULT NULL,
  `cid` int(11) DEFAULT NULL,
  `psc` int(11) DEFAULT NULL,
  `range` int(11) DEFAULT NULL,
  `new_measures` int(10) unsigned DEFAULT NULL,
  `total_measures` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `cell_idx_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`),
  KEY `cell_created_idx` (`created`),
  KEY `cell_new_measures_idx` (`new_measures`),
  KEY `cell_total_measures_idx` (`total_measures`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cell_blacklist` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `time` datetime DEFAULT NULL,
  `radio` smallint(6) DEFAULT NULL,
  `mcc` smallint(6) DEFAULT NULL,
  `mnc` int(11) DEFAULT NULL,
  `lac` int(11) DEFAULT NULL,
  `cid` int(11) DEFAULT NULL,
  `count` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `cell_blacklist_idx_unique` (`radio`,`mcc`,`mnc`,`lac`,`cid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cell_measure` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `report_id` binary(16) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `time` datetime DEFAULT NULL,
  `accuracy` int(11) DEFAULT NULL,
  `altitude` int(11) DEFAULT NULL,
  `altitude_accuracy` int(11) DEFAULT NULL,
  `heading` float DEFAULT NULL,
  `speed` float DEFAULT NULL,
  `radio` smallint(6) DEFAULT NULL,
  `mcc` smallint(6) DEFAULT NULL,
  `mnc` int(11) DEFAULT NULL,
  `lac` int(11) DEFAULT NULL,
  `cid` int(11) DEFAULT NULL,
  `psc` int(11) DEFAULT NULL,
  `asu` smallint(6) DEFAULT NULL,
  `signal` smallint(6) DEFAULT NULL,
  `ta` smallint(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cell_measure_created_idx` (`created`),
  KEY `cell_measure_key_idx` (`radio`,`mcc`,`mnc`,`lac`,`cid`)
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
  UNIQUE KEY `mapstat_lat_lon_unique` (`lat`,`lon`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `measure_block` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `measure_type` smallint(6) DEFAULT NULL,
  `s3_key` varchar(80) DEFAULT NULL,
  `archive_date` datetime DEFAULT NULL,
  `archive_sha` binary(20) DEFAULT NULL,
  `start_id` bigint(20) unsigned DEFAULT NULL,
  `end_id` bigint(20) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_measure_block_archive_date` (`archive_date`),
  KEY `idx_measure_block_s3_key` (`s3_key`),
  KEY `idx_measure_block_end_id` (`end_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=4;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `score` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `userid` int(10) unsigned DEFAULT NULL,
  `key` smallint(6) DEFAULT NULL,
  `time` date DEFAULT NULL,
  `value` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `score_userid_key_time_unique` (`userid`,`key`,`time`),
  KEY `ix_score_userid` (`userid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `stat` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `key` smallint(6) DEFAULT NULL,
  `time` date DEFAULT NULL,
  `value` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `stat_key_time_unique` (`key`,`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nickname` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_nickname_unique` (`nickname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `created` datetime DEFAULT NULL,
  `key` varchar(12) DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `max_lat` double DEFAULT NULL,
  `min_lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `max_lon` double DEFAULT NULL,
  `min_lon` double DEFAULT NULL,
  `range` int(11) DEFAULT NULL,
  `new_measures` int(10) unsigned DEFAULT NULL,
  `total_measures` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `wifi_key_unique` (`key`),
  KEY `wifi_created_idx` (`created`),
  KEY `wifi_new_measures_idx` (`new_measures`),
  KEY `wifi_total_measures_idx` (`total_measures`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_blacklist` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `time` datetime DEFAULT NULL,
  `key` varchar(12) DEFAULT NULL,
  `count` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `wifi_blacklist_key_unique` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `wifi_measure` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `report_id` binary(16) DEFAULT NULL,
  `created` datetime DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lon` double DEFAULT NULL,
  `time` datetime DEFAULT NULL,
  `accuracy` int(11) DEFAULT NULL,
  `altitude` int(11) DEFAULT NULL,
  `altitude_accuracy` int(11) DEFAULT NULL,
  `heading` float DEFAULT NULL,
  `speed` float DEFAULT NULL,
  `key` varchar(12) DEFAULT NULL,
  `channel` smallint(6) DEFAULT NULL,
  `signal` smallint(6) DEFAULT NULL,
  `snr` smallint(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `wifi_measure_created_idx` (`created`),
  KEY `wifi_measure_key_idx` (`key`),
  KEY `wifi_measure_key_created_idx` (`key`,`created`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
