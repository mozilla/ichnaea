-- Running upgrade 4c89b299ffb0 -> 5214b5cfc5d2

CREATE INDEX cell_modified_idx ON cell (modified);

UPDATE alembic_version SET version_num='5214b5cfc5d2';
