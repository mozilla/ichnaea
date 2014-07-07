-- Running upgrade 5357bcae9bfe -> 45059acb751f

ALTER TABLE cell_measure DROP COLUMN measure_id;

ALTER TABLE wifi_measure DROP COLUMN measure_id;

DROP TABLE measure;

UPDATE alembic_version SET version_num='45059acb751f';
