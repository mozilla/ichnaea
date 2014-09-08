-- Running upgrade 294707f1a078 -> 4c89b299ffb0

DELETE FROM ocid_cell;

ALTER TABLE ocid_cell DROP PRIMARY KEY, CHANGE COLUMN `id` `id` bigint(20) unsigned, ADD PRIMARY KEY(radio, mcc, mnc, lac, cid), DROP KEY ocid_cell_idx_unique;

ALTER TABLE ocid_cell CHANGE COLUMN lac lac smallint(5) unsigned, CHANGE COLUMN cid cid int(10) unsigned;

ALTER TABLE ocid_cell DROP COLUMN `id`;

UPDATE alembic_version SET version_num='4c89b299ffb0';
