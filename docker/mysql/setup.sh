#!/bin/bash

echo "=> Starting mysql"
/entrypoint.sh mysqld > /dev/null 2>&1 &

# Wait to confirm that it has started.
RET=1
while [[ RET -ne 0 ]]; do
    sleep 1
    mysql -uroot -pmysql -e "status" > /dev/null 2>&1
    RET=$?
done
echo "=> Mysql started"

# Create default databases.
echo "=> Create location database"
mysql -uroot -pmysql --protocol=socket \
    -e "CREATE DATABASE IF NOT EXISTS location"
mysql -uroot -pmysql --protocol=socket \
    -e "CREATE DATABASE IF NOT EXISTS test_location"

# Stop the server.
echo "=> Stopping mysql"
mysqladmin -uroot -pmysql shutdown
