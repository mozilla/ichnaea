CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL
);

-- Running upgrade None -> 2a311d11a90d

CREATE TABLE api_key (
    valid_key VARCHAR(36) NOT NULL, 
    PRIMARY KEY (valid_key)
)ENGINE=InnoDB CHARSET=utf8;

INSERT INTO alembic_version (version_num) VALUES ('2a311d11a90d');

