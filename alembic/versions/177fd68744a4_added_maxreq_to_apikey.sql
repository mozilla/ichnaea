-- Running upgrade 10f2bbd0fdaa -> 177fd68744a4

ALTER TABLE api_key ADD COLUMN maxreq INTEGER;

UPDATE alembic_version SET version_num='177fd68744a4';
