-- Running upgrade 177fd68744a4 -> 383a10fbb4c8

ALTER TABLE cell_measure ADD COLUMN report_id BINARY(16) AFTER id;

ALTER TABLE wifi_measure ADD COLUMN report_id BINARY(16) AFTER id;

UPDATE alembic_version SET version_num='383a10fbb4c8';
