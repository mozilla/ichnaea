-- Running upgrade 2a311d11a90d -> 51ba8090058d

ALTER TABLE api_key MODIFY valid_key VARCHAR(40) NULL;

UPDATE alembic_version SET version_num='51ba8090058d';

