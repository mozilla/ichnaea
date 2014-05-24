-- Running upgrade 51ba8090058d -> 4323e1f1a0b8

CREATE TABLE measure_block (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, 
    measure_type SMALLINT, 
    s3_key VARCHAR(80), 
    archive_date DATETIME, 
    archive_sha BINARY(20), 
    start_id BIGINT UNSIGNED, 
    end_id BIGINT UNSIGNED, 
    PRIMARY KEY (id)
)ENGINE=InnoDB ROW_FORMAT=compressed CHARSET=utf8 KEY_BLOCK_SIZE=4;

CREATE INDEX idx_measure_block_archive_date ON measure_block (archive_date);

CREATE INDEX idx_measure_block_s3_key ON measure_block (s3_key);

CREATE INDEX idx_measure_block_end_id ON measure_block (end_id);

UPDATE alembic_version SET version_num='4323e1f1a0b8';

